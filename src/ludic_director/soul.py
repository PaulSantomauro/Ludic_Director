from __future__ import annotations


class Soul:
    """
    Persistent director identity loaded from a markdown file.
    Injected as a preamble into prompts so layers share the same persona.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._content: str = self._load()

    def _load(self) -> str:
        try:
            with open(self.path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    def read(self) -> str:
        return self._content

    def as_prompt_preamble(self) -> str:
        if not self._content:
            return ""
        return f"## Your Identity (Soul)\n{self._content}\n\n"

    def update_section(self, section_header: str, new_body: str) -> None:
        """Replace the body under a ## heading (first match, case-insensitive substring)."""
        lines = self._content.split("\n")
        out: list[str] = []
        in_section = False
        replaced = False
        for line in lines:
            if line.strip().startswith("## ") and section_header.lower() in line.lower():
                out.append(line)
                out.append(new_body.strip())
                in_section = True
                replaced = True
                continue
            if in_section and line.startswith("## "):
                in_section = False
            if not in_section:
                out.append(line)
        if not replaced:
            out.append(f"\n## {section_header}\n{new_body.strip()}")
        self._content = "\n".join(out)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self._content)
        except OSError:
            pass
