# One-off setup for the realistic anchor (channel/avatar.py) on Windows with an NVIDIA GPU.
# Installs SadTalker in its own folder with its own Python 3.10 environment (its pinned
# packages don't build on 3.12), downloads the model weights (~1 GB; -Full adds
# the 512 px model and the face enhancer, ~1.1 GB more) and adds the paths to GRAD0\.env.   Run:  powershell -ExecutionPolicy Bypass -File tools\setup_sadtalker.ps1
param([string]$Dir = "$env:USERPROFILE\SadTalker", [switch]$Full)
$ErrorActionPreference = "Continue"   # native tools (git, uv) write progress to stderr; failures are checked by exit code
$Repo = Split-Path -Parent $PSScriptRoot

function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }

Step "SadTalker code -> $Dir"
if (-not (Test-Path "$Dir\inference.py")) { git clone --depth 1 https://github.com/OpenTalker/SadTalker.git $Dir }

Step "Python 3.10 environment (via uv)"
python -m pip install --quiet --upgrade uv
if (-not (Test-Path "$Dir\venv\Scripts\python.exe")) {
  python -m uv python install 3.10 2>&1 | Out-Host     # may warn about the version link on Windows; the interpreter is still there
  $py310 = Get-ChildItem "$env:APPDATA\uv\python\cpython-3.10.*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  python -m uv venv --python $(if ($py310) { $py310.FullName } else { "3.10" }) "$Dir\venv"
}
$Py = "$Dir\venv\Scripts\python.exe"
function UvPip { python -m uv pip install --python $Py @args; if ($LASTEXITCODE) { throw "pip install failed: $args" } }

Step "PyTorch with CUDA"
# torchvision 0.15 still has transforms.functional_tensor, which basicsr/gfpgan import
UvPip torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

Step "SadTalker packages"
UvPip "numpy==1.23.5" "face_alignment==1.3.5" "imageio==2.19.3" "imageio-ffmpeg==0.4.7" "librosa==0.9.2" `
      "numba" "resampy==0.3.1" "pydub==0.25.1" "scipy==1.10.1" "kornia==0.6.8" "tqdm" "yacs==0.1.8" "pyyaml" `
      "joblib==1.1.0" "scikit-image==0.19.3" "basicsr==1.4.2" "facexlib==0.3.0" "gfpgan" "av" "safetensors" `
      "opencv-python==4.8.1.78" "setuptools<70"   # librosa 0.9 imports pkg_resources

Step "Model weights"
$rel = "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc"
$gfp = "https://github.com/xinntao/facexlib/releases/download"
$files = @(
  @("$rel/mapping_00109-model.pth.tar", "checkpoints\mapping_00109-model.pth.tar"),
  @("$rel/mapping_00229-model.pth.tar", "checkpoints\mapping_00229-model.pth.tar"),
  @("$rel/SadTalker_V0.0.2_256.safetensors", "checkpoints\SadTalker_V0.0.2_256.safetensors"),
  @("$gfp/v0.1.0/alignment_WFLW_4HG.pth", "gfpgan\weights\alignment_WFLW_4HG.pth"),        # face landmarks (always needed)
  @("$gfp/v0.1.0/detection_Resnet50_Final.pth", "gfpgan\weights\detection_Resnet50_Final.pth")
)
if ($Full) {   # -Full: the 512 px model and the GFPGAN face enhancer (PEN_ANCHOR_ENHANCE=1), ~1.1 GB more
  $files += ,@("$rel/SadTalker_V0.0.2_512.safetensors", "checkpoints\SadTalker_V0.0.2_512.safetensors")
  $files += ,@("https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth", "gfpgan\weights\GFPGANv1.4.pth")
  $files += ,@("$gfp/v0.2.2/parsing_parsenet.pth", "gfpgan\weights\parsing_parsenet.pth")
}
foreach ($f in $files) {
  $out = Join-Path $Dir $f[1]
  if ((Test-Path $out) -and (Get-Item $out).Length -gt 1MB) { continue }
  New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
  Write-Host "  $($f[1])"
  curl.exe -L --fail --retry 3 -o $out $f[0]
  if ($LASTEXITCODE) { throw "download failed: $($f[0])" }
}

Step "GPU check"
& $Py -c "import torch;print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"

Step "Paths -> .env"
$envFile = Join-Path $Repo ".env"
if (-not (Select-String -Path $envFile -Pattern '^PEN_SADTALKER_DIR=' -Quiet -ErrorAction SilentlyContinue)) {
  Add-Content -Encoding ascii $envFile "`nPEN_SADTALKER_DIR=$Dir`nPEN_SADTALKER_PYTHON=$Py"
}
Write-Host "Done. Next: python -m channel.avatar --once"
