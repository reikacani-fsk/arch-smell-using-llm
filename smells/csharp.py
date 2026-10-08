"""C# support: tree-sitter-c-sharp parsing, skeletons (C1) and the class dependency graph.

C# has no jdeps, so the class graph is resolved from source: every identifier inside a top-level type is
looked up against the project's own types, following C# scoping (enclosing namespaces, using directives,
using aliases, using static, qualified names). This is name-based, not Roslyn's semantic model: it misses
references that never spell out a type name (e.g. members of a `var` local) and can add an edge when a
local or parameter shares a project type's name. Nested types are folded into their outer type, as for jdeps.
"""
from pathlib import Path

import networkx as nx
import tree_sitter_c_sharp as tscs
from tree_sitter import Language, Parser

CSHARP = Language(tscs.language())
TYPE_NODES = {"class_declaration", "interface_declaration", "struct_declaration", "enum_declaration",
              "record_declaration", "record_struct_declaration", "delegate_declaration"}
NAMESPACES = {"namespace_declaration", "file_scoped_namespace_declaration"}
PREPROC = {"preproc_if", "preproc_elif", "preproc_else"}   # #if blocks wrap the declarations they guard
MEMBER_SIGS = {"method_declaration", "constructor_declaration", "destructor_declaration",
               "operator_declaration", "conversion_operator_declaration"}
PROPERTIES = {"property_declaration", "indexer_declaration", "event_declaration"}
FIELDS = {"field_declaration", "event_field_declaration"}
NAME_IS_REF = {"qualified_name", "generic_name", "alias_qualified_name"}   # elsewhere `name` declares


def _parser():
    return Parser(CSHARP)


def _text(node) -> str:
    return " ".join(node.text.decode("utf-8", "replace").split())


def _name(node) -> str:
    return "".join(node.text.decode("utf-8", "replace").split()).replace("global::", "")


def _children(container):
    """Named children, with #if/#else blocks flattened into their parent."""
    for c in container.named_children:
        if c.type in PREPROC:
            yield from _children(c)
        else:
            yield c


def _using(node):
    """(kind, alias, target) for a using directive; kind is 'static', 'global' or 'plain'."""
    kinds = {c.type for c in node.children if not c.is_named}
    alias = node.child_by_field_name("name")
    target = [c for c in node.named_children if c != alias and c.type != "comment"]
    kind = "static" if "static" in kinds else "global" if "global" in kinds else "plain"
    return kind, alias.text.decode() if alias is not None else None, _name(target[-1]) if target else ""


def _walk(root):
    """Yield (type_node, namespace, usings) for every top-level type; usings are those visible in scope."""
    out = []

    def visit(container, ns, usings):
        usings = list(usings)
        kids = list(_children(container))
        usings += [_using(c) for c in kids if c.type == "using_directive"]
        for c in kids:
            if c.type == "file_scoped_namespace_declaration":   # applies to the rest of the file
                ns = _name(c.child_by_field_name("name"))
                visit(c, ns, usings)
            elif c.type == "namespace_declaration":
                name = _name(c.child_by_field_name("name"))
                visit(c.child_by_field_name("body"), f"{ns}.{name}" if ns else name, usings)
            elif c.type in TYPE_NODES:
                out.append((c, ns, usings))

    visit(root, "", [])
    return out


def parse(text: bytes):
    """(primary namespace, top-level type names, [(type_node, namespace, usings)]) of one file."""
    tree = _parser().parse(text.removeprefix(b"\xef\xbb\xbf"))
    decls =[(n, ns, u) for n, ns, u in _walk(tree.root_node) if n.child_by_field_name("name") is not None]
    names = [n.child_by_field_name("name").text.decode() for n, _, _ in decls]
    return (decls[0][1] if decls else ""), names, decls


# ---------------------------------------------------------------- skeleton (C1, RAG)

def _head(node, src, stops) -> str:
    """Node text up to the first child whose type is in `stops`, whitespace collapsed."""
    end = next((c.start_byte for c in node.children if c.type in stops), node.end_byte)
    return " ".join(src[node.start_byte:end].decode("utf-8", "replace").split())


def _skeleton_type(node, src, indent, out):
    pad = " " * indent
    body = node.child_by_field_name("body")
    if body is None:                                   # delegate, record without body
        out.append(pad + _text(node))
        return
    out.append(pad + _head(node, src, {body.type}) + " {")
    for child in _children(body):
        if child.type in TYPE_NODES:
            _skeleton_type(child, src, indent + 4, out)
        elif child.type in FIELDS:
            out.append(pad + "    " + _text(child))
        elif child.type in MEMBER_SIGS:
            out.append(pad + "    " + _head(child, src, {"block", "arrow_expression_clause"}).rstrip(";") + ";")
        elif child.type in PROPERTIES:
            acc = child.child_by_field_name("accessors")
            parts = [_head(a, src, {"block", "arrow_expression_clause"}).rstrip(";") + ";"
                     for a in acc.named_children if a.type == "accessor_declaration"] if acc else ["get;"]
            head = _head(child, src, {"accessor_list", "arrow_expression_clause", "="})
            out.append(pad + "    " + head + " { " + " ".join(parts) + " }")
        elif child.type == "enum_member_declaration":
            n = child.child_by_field_name("name")
            out.append(pad + "    " + (n.text.decode() if n is not None else "?") + ",")
    out.append(pad + "}")


def skeleton(text: str) -> str:
    """Usings, namespaces, type headers, fields and member signatures; no method bodies or comments."""
    src = text.encode("utf-8")
    out = []

    def visit(container):
        for node in _children(container):
            if node.type == "using_directive":
                out.append(_text(node))
            elif node.type in NAMESPACES:
                out.append("namespace " + _name(node.child_by_field_name("name")))
                visit(node.child_by_field_name("body") or node)
            elif node.type in TYPE_NODES:
                _skeleton_type(node, src, 0, out)

    visit(_parser().parse(src).root_node)
    return "\n".join(out)


# ---------------------------------------------------------------- dependency graph (replaces jdeps)

def _dotted(node):
    """['A', 'B', 'C'] for A.B.C as a qualified name or member access chain, else None."""
    if node is None:
        return None
    if node.type == "identifier":
        return [node.text.decode()]
    if node.type == "generic_name":
        return [node.named_children[0].text.decode()]
    if node.type == "alias_qualified_name":                       # global::A.B
        return _dotted(node.child_by_field_name("name"))
    if node.type in ("qualified_name", "member_access_expression"):
        left = _dotted(node.child_by_field_name("qualifier") or node.child_by_field_name("expression"))
        right = _dotted(node.child_by_field_name("name"))
        return left + right if left and right else None
    return None


def _references(type_node):
    """Simple identifiers that may name a type, and dotted chains that may contain a qualified type name."""
    simple, dotted = set(), set()
    stack = [type_node]
    while stack:
        n = stack.pop()
        if n.type in ("qualified_name", "member_access_expression"):
            parts = _dotted(n)
            if parts and len(parts) > 1:
                dotted.add(tuple(parts))
        for i, c in enumerate(n.children):
            if not c.is_named or c.type == "comment":
                continue
            if c.type == "identifier":
                if n.field_name_for_child(i) != "name" or n.type in NAME_IS_REF:
                    simple.add(c.text.decode())
            else:
                stack.append(c)
    return simple, dotted


def _chain(ns: str):
    """Enclosing namespaces, innermost first: A.B -> [A.B, A, '']."""
    parts = ns.split(".") if ns else []
    return [".".join(parts[:i]) for i in range(len(parts), -1, -1)]


class _Scope:
    """Name lookup for one top-level type, following C# rules closely enough for a dependency graph."""

    def __init__(self, ns, usings, types_by_ns, fqns):
        self.ns, self.types_by_ns, self.fqns = ns, types_by_ns, fqns
        self.opened, self.aliases, self.statics = [], {}, []
        for kind, alias, target in usings:
            if alias:
                self.aliases[alias] = self.qualified(target.split("."), allow_alias=False) or target
            elif kind == "static":
                fq = self.qualified(target.split("."), allow_alias=False)
                if fq:
                    self.statics.append(fq)
            else:                       # a using inside a namespace may be relative to it
                self.opened.append(next((f"{n}.{target}" if n else target for n in _chain(ns)
                                         if (f"{n}.{target}" if n else target) in types_by_ns), target))

    def simple(self, name):
        for n in _chain(self.ns):
            hit = self.types_by_ns.get(n, {}).get(name)
            if hit:
                return hit
        if name in self.aliases:
            return self.aliases[name] if self.aliases[name] in self.fqns else None
        hits = {self.types_by_ns[u][name] for u in self.opened if name in self.types_by_ns.get(u, {})}
        return hits.pop() if len(hits) == 1 else None             # ambiguous: would not compile

    def qualified(self, parts, allow_alias=True):
        """Longest prefix of A.B.C that is a project type, absolute or relative to an enclosing namespace."""
        if allow_alias and parts[0] in self.aliases:
            parts = self.aliases[parts[0]].split(".") + list(parts[1:])
        for k in range(len(parts), 0, -1):
            dotted = ".".join(parts[:k])
            for n in _chain(self.ns):
                fq = f"{n}.{dotted}" if n else dotted
                if fq in self.fqns:
                    return fq
        return None


def class_graph(source_dirs, prefix: str) -> nx.DiGraph:
    """Class-level graph (nested types folded into their outer type), project types only."""
    decls = []
    for d in source_dirs:
        for p in sorted(Path(d).rglob("*.cs")):
            _, _, file_decls = parse(p.read_bytes())
            decls += file_decls
    global_usings = [u for _, _, usings in decls for u in usings if u[0] == "global"]
    types_by_ns, fqns = {}, set()
    for node, ns, _ in decls:
        name = node.child_by_field_name("name").text.decode()
        fq = f"{ns}.{name}" if ns else name
        types_by_ns.setdefault(ns, {})[name] = fq
        fqns.add(fq)
    g = nx.DiGraph()
    for node, ns, usings in decls:
        name = node.child_by_field_name("name").text.decode()
        src = f"{ns}.{name}" if ns else name
        if not src.startswith(prefix):
            continue
        g.add_node(src)
        scope = _Scope(ns, global_usings + usings, types_by_ns, fqns)
        simple, dotted = _references(node)
        targets = {scope.simple(s) for s in simple} | {scope.qualified(list(d)) for d in dotted}
        targets |= set(scope.statics)
        for dst in targets:
            if dst and dst != src and dst.startswith(prefix):
                g.add_edge(src, dst)
    return g


def write_edges(g: nx.DiGraph, path: Path) -> Path:
    """Class edges in jdeps-like text form, kept for auditing the graph."""
    path.write_text("\n".join(f"   {a} -> {b}" for a, b in sorted(g.edges)) + "\n", encoding="utf-8")
    return path
