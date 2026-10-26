import pytest

from limpaper.library import Library, LibraryError, clean_category, pretty


def test_pretty_names():
    assert pretty("neon-grid.1920x1080.mp4") == "neon grid"
    assert pretty("sub/city_rain.mp4") == "city rain"
    assert pretty("crimson-abyss-moewalls-com.mp4") == "crimson abyss"
    assert pretty("no-extension") == "no extension"


def test_categories_skip_hidden(library):
    assert Library(library).categories() == ["abstract", "cars", "scenery"]


def test_wallpapers_loose_files_first(library):
    walls = Library(library).wallpapers("scenery")
    assert [w.rel for w in walls] == ["sunset.png", "night/city_rain.mp4"]
    assert walls[1].subfolder == "night"
    assert walls[0].kind == "image" and walls[1].kind == "video"


def test_all_and_counts(library):
    lib = Library(library)
    assert len(lib.wallpapers()) == 5
    assert lib.count("abstract") == 2


def test_find(library):
    lib = Library(library)
    assert lib.find("neon grid").rel == "neon-grid.1920x1080.mp4"
    assert lib.find("cars/r31.mkv").category == "cars"
    assert lib.find(str(library / "cars" / "r31.mkv")).category == "cars"
    assert lib.find("nothing like this") is None


def test_add_move_delete(library, tmp_path):
    lib = Library(library)
    src = tmp_path / "new.mp4"
    src.write_bytes(b"y")
    junk = tmp_path / "virus.exe"
    junk.write_bytes(b"MZ")
    added = lib.add([src, junk], "fresh")
    assert [p.name for p in added] == ["new.mp4"]
    assert src.exists()  # copied, not moved
    again = lib.add([src], "fresh")
    assert again[0].name == "new (2).mp4"
    w = lib.find("cars/r31.mkv")
    dest = lib.move(w, "fresh")
    assert dest.parent.name == "fresh" and not w.path.exists()
    lib.delete(lib.find(str(dest)))
    assert not dest.exists()


def test_add_nothing_valid_creates_no_category(library, tmp_path):
    junk = tmp_path / "a.txt"
    junk.write_text("x")
    assert Library(library).add([junk], "ghost") == []
    assert not (library / "ghost").exists()


def test_category_validation(library):
    lib = Library(library)
    for bad in ("", ".hidden", "a/b", "..", "x:y"):
        with pytest.raises(LibraryError):
            clean_category(bad)
    lib.create_category("empty")
    lib.rename_category("empty", "renamed")
    assert "renamed" in lib.categories()
    with pytest.raises(LibraryError):
        lib.delete_category("abstract")
    lib.delete_category("renamed")
    assert "renamed" not in lib.categories()
