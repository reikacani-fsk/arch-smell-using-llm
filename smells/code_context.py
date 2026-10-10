"""C1 context: source code of a package, parsed with tree-sitter-java (C#: see csharp.py)."""
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_java as tsj
from tree_sitter import Language, Parser

JAVA = Language(tsj.language())
TYPE_NODES = {"class_declaration", "interface_declaration", "enum_declaration",
              "record_declaration", "annotation_type_declaration"}
MEMBER_SIGS = {"method_declaration", "constructor_declaration", "compact_constructor_declaration",
               "annotation_type_element_declaration"}


@dataclass
class SourceFile:
    path: Path
    package: str
    text: str
    types: list = field(default_factory=list)   # top-level type names
    loc: int = 0                                 # non-blank lines
    language: str = "java"


def _parser():
    return Parser(JAVA)


def _loc(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def parse_csharp_file(path: Path) -> SourceFile:
    """A C# file is assigned to the namespace of its first top-level type."""
    from .csharp import parse
    src = path.read_bytes()
    ns, types, _ = parse(src)
    text = src.decode("utf-8-sig", "replace")
    return SourceFile(path, ns, text, types, _loc(text), "csharp")


def parse_file(path: Path) -> SourceFile:
    src = path.read_bytes()
    tree = _parser().parse(src)
    pkg, types = "", []
    for node in tree.root_node.named_children:
        if node.type == "package_declaration":
            pkg = src[node.start_byte:node.end_byte].decode("utf-8", "replace")
            pkg = pkg.replace("package", "", 1).replace(";", "").strip()
        elif node.type in TYPE_NODES:
            name = node.child_by_field_name("name")
            if name is not None:
                types.append(name.text.decode())
    text = src.decode("utf-8", "replace")
    return SourceFile(path, pkg, text, types, _loc(text))


def index_sources(source_dirs, language="java") -> dict:
    """package name -> list[SourceFile]"""
    index = defaultdict(list)
    if language == "csharp":
        from .csharp import cs_files
        for d in source_dirs:
            for p in cs_files(d):
                sf = parse_csharp_file(p)
                if sf.types:                       # skips AssemblyInfo.cs and similar
                    index[sf.package].append(sf)
        return dict(index)
    for d in source_dirs:
        for p in sorted(Path(d).rglob("*.java")):
            if p.name in ("package-info.java", "module-info.java"):
                continue
            sf = parse_file(p)
            index[sf.package].append(sf)
    return dict(index)


def package_size(index) -> dict:
    """package -> (loc, number of top-level types); a C# partial type split over files counts once"""
    return {pkg: (sum(f.loc for f in files), len({t for f in files for t in f.types}))
            for pkg, files in index.items()}


def _skeleton_node(node, src, indent, out):
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    out.append(" " * indent + " ".join(src[node.start_byte:end].decode("utf-8", "replace").split()) + " {")
    if body is not None:
        for child in body.named_children:
            if child.type in TYPE_NODES:
                _skeleton_node(child, src, indent + 4, out)
            elif child.type == "field_declaration" or child.type == "constant_declaration":
                out.append(" " * (indent + 4) + " ".join(child.text.decode("utf-8", "replace").split()))
            elif child.type in MEMBER_SIGS:
                b = child.child_by_field_name("body")
                stop = b.start_byte if b is not None else child.end_byte
                sig = " ".join(src[child.start_byte:stop].decode("utf-8", "replace").split())
                out.append(" " * (indent + 4) + sig.rstrip(";") + ";")
            elif child.type == "enum_constant":
                n = child.child_by_field_name("name")
                out.append(" " * (indent + 4) + (n.text.decode() if n is not None else "?") + ",")
    out.append(" " * indent + "}")


def skeleton(text: str, language="java") -> str:
    """Imports, type headers, fields and member signatures; no method bodies or comments."""
    if language == "csharp":
        from .csharp import skeleton as cs_skeleton
        return cs_skeleton(text)
    src = text.encode("utf-8")
    tree = _parser().parse(src)
    out = []
    for node in tree.root_node.named_children:
        if node.type in ("package_declaration", "import_declaration"):
            out.append(node.text.decode("utf-8", "replace"))
        elif node.type in TYPE_NODES:
            _skeleton_node(node, src, 0, out)
    return "\n".join(out)


def package_code_context(package: str, index: dict, max_chars: int) -> str:
    files = index.get(package, [])
    full = "\n\n".join(f"// File: {f.path.name}\n{f.text}" for f in files)
    if len(full) <= max_chars:
        return f"[Full source of package {package}, {len(files)} files]\n\n{full}"
    skel = "\n\n".join(f"// File: {f.path.name}\n{skeleton(f.text, f.language)}" for f in files)
    note = f"[Package {package} is large ({len(files)} files); showing skeletons: imports, fields, signatures]"
    if len(skel) > max_chars:
        skel = skel[:max_chars] + "\n// ... truncated: package exceeds context budget ..."
    return f"{note}\n\n{skel}"
