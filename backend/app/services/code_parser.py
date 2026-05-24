import os
from pathlib import Path
from typing import Any

LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".md": "Markdown",
    ".toml": "TOML",
}

FRAMEWORK_HINTS = {
    "next.config": "Next.js",
    "nuxt.config": "Nuxt",
    "vite.config": "Vite",
    "angular.json": "Angular",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "express": "Express",
    "react": "React",
    "vue": "Vue",
    "tailwind": "TailwindCSS",
    "prisma": "Prisma",
    "supabase": "Supabase",
    "docker-compose": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".pytest_cache",
    "target", "vendor", ".idea", ".vscode", "bin", "obj",
}

DEP_FILES = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "poetry",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "Gemfile": "bundler",
}


class CodeParser:
    """Parse repository structure, languages, and complexity."""

    def analyze(self, repo_path: Path) -> dict[str, Any]:
        languages: dict[str, int] = {}
        file_count = 0
        total_lines = 0
        folder_structure: list[str] = []
        file_sizes: list[tuple[str, int, int]] = []
        dependencies: dict[str, list[str]] = {}
        frameworks: set[str] = set()

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            rel_root = Path(root).relative_to(repo_path)
            if str(rel_root) != ".":
                folder_structure.append(str(rel_root).replace("\\", "/"))

            for fname in files:
                fpath = Path(root) / fname
                rel_path = fpath.relative_to(repo_path)
                ext = fpath.suffix.lower()

                if ext in LANGUAGE_MAP:
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore")
                        lines = len(content.splitlines())
                        lang = LANGUAGE_MAP[ext]
                        languages[lang] = languages.get(lang, 0) + lines
                        file_count += 1
                        total_lines += lines
                        file_sizes.append((str(rel_path).replace("\\", "/"), lines, len(content)))
                    except (OSError, PermissionError):
                        continue

                if fname in DEP_FILES:
                    deps = self._parse_dependencies(fpath, fname)
                    if deps:
                        dependencies[DEP_FILES[fname]] = deps

                for hint, fw in FRAMEWORK_HINTS.items():
                    if hint in fname.lower() or hint in str(rel_path).lower():
                        frameworks.add(fw)

        file_sizes.sort(key=lambda x: x[1], reverse=True)
        hotspots = [
            {"file": f, "lines": lines, "size_bytes": size}
            for f, lines, size in file_sizes[:10]
        ]

        folder_structure = sorted(set(folder_structure))[:50]

        return {
            "languages": languages,
            "frameworks": sorted(frameworks),
            "file_count": file_count,
            "total_lines": total_lines,
            "folder_structure": folder_structure,
            "complexity_hotspots": hotspots,
            "dependencies": dependencies,
        }

    def _parse_dependencies(self, path: Path, filename: str) -> list[str]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        deps: list[str] = []
        if filename == "package.json":
            import json
            data = json.loads(text)
            for key in ("dependencies", "devDependencies"):
                deps.extend(data.get(key, {}).keys())
        elif filename == "requirements.txt":
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(line.split("==")[0].split(">=")[0].split("[")[0].strip())
        elif filename == "pyproject.toml":
            in_deps = False
            for line in text.splitlines():
                if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
                    in_deps = True
                    continue
                if in_deps and line.startswith("["):
                    break
                if in_deps and "=" in line:
                    deps.append(line.split("=")[0].strip().strip('"'))
        return deps[:30]

    def read_key_files(self, repo_path: Path, max_chars: int = 8000) -> str:
        """Read README and config files for context."""
        priority = [
            "README.md", "readme.md", "README.rst",
            "package.json", "pyproject.toml", "requirements.txt",
            "docker-compose.yml", "Dockerfile",
            "main.py", "app.py", "index.ts", "index.js",
        ]
        chunks: list[str] = []
        total = 0

        for name in priority:
            for candidate in repo_path.rglob(name):
                if any(p in candidate.parts for p in SKIP_DIRS):
                    continue
                try:
                    content = candidate.read_text(encoding="utf-8", errors="ignore")
                    rel = candidate.relative_to(repo_path)
                    snippet = content[:2000]
                    block = f"\n--- {rel} ---\n{snippet}\n"
                    if total + len(block) > max_chars:
                        break
                    chunks.append(block)
                    total += len(block)
                except OSError:
                    continue
            if total >= max_chars:
                break

        return "".join(chunks)
