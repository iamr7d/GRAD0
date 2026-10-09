# Audio credits

| File | What | Source / licence |
|---|---|---|
| `bed.m4a` | News music bed (loops under the anchor, ducked while the voice plays) | Original, synthesised for this channel by `channel/make_music.py`; no third-party material |
| `sting.m4a` | Logo sting on the opening titles and end card | Original, synthesised by `channel/make_music.py` |

## Local override (not in git)
`channel/server.py` serves `bucket/media/music/news_bed.*` and `news_sting.*` in place of the files above
when they exist (first match alphabetically, so a `.m4a` wins over an `.mp3`). Those files stay out of
git because stock-music licences (e.g. Pixabay Content Licence) allow use in videos but not
re-distributing the audio files themselves.

On the owner's PC (Oct 2026): `news_bed.mp3`, `news_bed_alt1.mp3` and `news_bed_alt2.mp3` were downloaded
on 8 Oct 2026; the files carry no tags, so **record the track title, artist and page URL here** before
publishing a video that uses them. `news_bed.m4a` is the same track loudness-normalised to -20 LUFS
(`ffmpeg -i news_bed.mp3 -af loudnorm=I=-20:TP=-2 ...`) so it sits under the -16 LUFS voice like the built-in bed.

| Local file | Track | Artist | Source URL | Licence |
|---|---|---|---|---|
| news_bed.mp3 | ? | ? | ? | ? |
