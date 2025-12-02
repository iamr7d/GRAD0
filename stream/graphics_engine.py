from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

class NewsGraphics:
    def __init__(self, width=1920, height=1080):
        self.W, self.H = width, height
        # Define Professional News Colors
        self.COLOR_BG = (10, 20, 40, 230)      # Dark Blue (Semi-Transparent)
        self.COLOR_ACCENT = (200, 0, 0, 255)   # Red Accent
        self.COLOR_TEXT = (255, 255, 255, 255) # White
        self.COLOR_HEADLINE = (255, 215, 0, 255) # Gold
        
        # Load Fonts (Use default system fonts if custom ones aren't found)
        try:
            # Try to find a bold font (Adjust path for Linux)
            self.font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            self.font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        except:
            self.font_main = ImageFont.load_default()
            self.font_sub = ImageFont.load_default()

    def create_overlay(self, main_heading, headlines, output_path):
        # 1. Create a transparent canvas
        img = Image.new('RGBA', (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 2. Draw the "Side Bar" or "Lower Third" box
        # Let's do a Left-Side Panel style (Like Bloomberg/CNBC)
        panel_w = 600
        panel_h = self.H - 200 # Leave room for ticker at bottom
        
        # Draw Background Box
        draw.rectangle([(50, 100), (50 + panel_w, 100 + panel_h)], fill=self.COLOR_BG)
        
        # Draw Red Accent Line at top
        draw.rectangle([(50, 100), (50 + panel_w, 110)], fill=self.COLOR_ACCENT)
        
        # 3. Draw Main Heading (Gold)
        # Wrap text if too long
        lines = textwrap.wrap(main_heading, width=20)
        y_text = 150
        for line in lines:
            draw.text((80, y_text), line, font=self.font_main, fill=self.COLOR_HEADLINE)
            y_text += 70
            
        # 4. Draw Bullet Points (White)
        y_text += 50
        for point in headlines:
            # Add bullet symbol
            wrapped_point = textwrap.wrap(f"• {point}", width=30)
            for subline in wrapped_point:
                draw.text((80, y_text), subline, font=self.font_sub, fill=self.COLOR_TEXT)
                y_text += 50
            y_text += 20 # Extra spacing between bullets
            
        # 5. Save
        img.save(output_path)
        print(f"🎨 Graphic Generated: {output_path}")