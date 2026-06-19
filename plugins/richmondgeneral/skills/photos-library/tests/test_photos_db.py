import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import photos_db

def test_original_relpath_uses_first_char_and_ext():
    rel = photos_db.original_relpath("ABC12345-0000-0000-0000-000000000000", "public.jpeg")
    assert rel == "originals/A/ABC12345-0000-0000-0000-000000000000.jpeg"

def test_original_relpath_heic_and_png():
    assert photos_db.original_relpath("b0000000-x", "public.heic").endswith(".heic")
    assert photos_db.original_relpath("b0000000-x", "public.png").endswith(".png")
