from utils.chunker import split_diff_into_chunks


def change(path, diff):
    return {"old_path": path, "new_path": path, "diff": diff}


def test_empty_changes_produce_no_chunks():
    assert split_diff_into_chunks([]) == []


def test_every_chunk_carries_its_file_header():
    changes = [change(f"src/file{i}.py", "@@ -1 +1 @@\n-a\n+b\n") for i in range(5)]
    chunks = split_diff_into_chunks(changes, max_chunk_size=80)
    assert chunks
    for chunk in chunks:
        assert chunk.startswith("File: ")


def test_small_changes_are_packed_together():
    changes = [change("a.py", "+1\n"), change("b.py", "+2\n")]
    chunks = split_diff_into_chunks(changes, max_chunk_size=1000)
    assert len(chunks) == 1
    assert "a.py" in chunks[0] and "b.py" in chunks[0]


def test_chunking_preserves_every_file():
    changes = [change(f"f{i}.py", "x" * 100) for i in range(10)]
    joined = "".join(split_diff_into_chunks(changes, max_chunk_size=150))
    for i in range(10):
        assert f"f{i}.py" in joined


def test_missing_new_path_falls_back_to_old_path():
    chunks = split_diff_into_chunks([{"old_path": "legacy.py", "diff": "-gone\n"}])
    assert "File: legacy.py" in chunks[0]
