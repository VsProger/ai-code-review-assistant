from typing import List, Dict, Any


def split_diff_into_chunks(
    diff_changes: List[Dict[str, Any]],
    max_chunk_size: int = 1500,
) -> List[str]:
    """
    diff_changes — список объектов из GitLab API:
    [
        {
            "old_path": "...",
            "new_path": "...",
            "diff": "@@ -10,7 +10,7 @@ ...",
        },
        ...
    ]

    Возвращает список строк (чанков), каждый не длиннее max_chunk_size символов.
    """

    chunks: List[str] = []
    current_chunk = ""

    for file_change in diff_changes:
        file_path = file_change.get("new_path") or file_change.get("old_path") or "unknown"
        file_header = f"File: {file_path}\n"
        file_diff = file_change.get("diff", "")

        block = file_header + file_diff + "\n\n"

        if len(current_chunk) + len(block) > max_chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = block
        else:
            current_chunk += block

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
