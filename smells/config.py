from pathlib import Path
import yaml


class Config(dict):
    """YAML config with paths resolved relative to the config file."""

    def __init__(self, path):
        self.file = Path(path).resolve()
        self.base = self.file.parent
        super().__init__(yaml.safe_load(self.file.read_text(encoding="utf-8")))

    def path(self, key):
        return (self.base / self[key]).resolve()

    @property
    def language(self):
        """'java' (default) or 'csharp'."""
        return self.get("language", "java")

    @property
    def project_root(self):
        return self.path("project_root")

    @property
    def source_dirs(self):
        return [self.project_root / d for d in self["source_dirs"]]

    @property
    def classes_dir(self):
        return self.project_root / self["classes_dir"]

    @property
    def data_dir(self):
        d = self.path("data_dir")
        d.mkdir(parents=True, exist_ok=True)
        return d
