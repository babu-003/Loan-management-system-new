Fonts used for Tamil PDFs (documents/pdf_generator.py picks the first one found).

FreeSerif.ttf / FreeSerifBold.ttf  - bundled so Tamil works out of the box.
  GNU FreeFont, GPLv3 with the font-embedding exception (embedding it in PDFs is fine).

For a cleaner, modern look, add Google's Noto fonts (SIL OFL, free) to this folder:
  NotoSansTamil-Regular.ttf, NotoSansTamil-Bold.ttf
  NotoSans-Regular.ttf, NotoSans-Bold.ttf   (Latin letters for English names/addresses)
They are picked automatically in preference to FreeSerif.
Or point settings.TAMIL_FONT_REGULAR / TAMIL_FONT_BOLD at any Tamil .ttf.
