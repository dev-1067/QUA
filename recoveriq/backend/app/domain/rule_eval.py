"""Safe evaluator for admin-written default rules such as `missed_emis >= 3 or dpd > 90`.
Parses with `ast` and walks a whitelist of node types: no names outside FIELDS, no calls,
no attributes, no subscripts. Never uses eval()."""
from __future__ import annotations

import ast
import operator

FIELDS = {
    "dpd": "Days past due",
    "missed_emis": "Missed EMIs",
    "outstanding": "Outstanding principal (₹)",
    "amount_due": "Overdue amount (₹)",
    "emi_amount": "EMI amount (₹)",
    "broken_ptp_count": "Broken promises",
    "risk_score": "Risk score (0-100)",
    "unreachable_streak": "Consecutive unreachable attempts",
}

_CMP = {ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Eq: operator.eq, ast.NotEq: operator.ne}
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


class RuleError(ValueError):
    pass


def _check(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _check(node.body)
    elif isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise RuleError("Only 'and' / 'or' are allowed")
        for v in node.values:
            _check(v)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.Not, ast.USub)):
            raise RuleError("Only 'not' and unary minus are allowed")
        _check(node.operand)
    elif isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _CMP:
                raise RuleError("Allowed comparisons: > >= < <= == !=")
        _check(node.left)
        for c in node.comparators:
            _check(c)
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _BIN:
            raise RuleError("Allowed arithmetic: + - * /")
        _check(node.left)
        _check(node.right)
    elif isinstance(node, ast.Name):
        if node.id not in FIELDS:
            raise RuleError(f"Unknown field '{node.id}'. Allowed: {', '.join(FIELDS)}")
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise RuleError("Only numeric constants are allowed")
    else:
        raise RuleError(f"'{type(node).__name__}' is not allowed in rules")


def compile_rule(expression: str) -> ast.Expression:
    expression = (expression or "").strip()
    if not expression or len(expression) > 300:
        raise RuleError("Rule must be 1-300 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise RuleError(f"Syntax error: {e.msg}") from None
    _check(tree)
    return tree


def _eval(node: ast.AST, env: dict):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.BoolOp):
        vals = (_eval(v, env) for v in node.values)
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, env)
        return (not v) if isinstance(node.op, ast.Not) else -v
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, env)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BinOp):
        r = _eval(node.right, env)
        if isinstance(node.op, ast.Div) and r == 0:
            return 0
        return _BIN[type(node.op)](_eval(node.left, env), r)
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise RuleError("unsupported")


def evaluate(tree: ast.Expression, case) -> bool:
    env = {f: (getattr(case, f, 0) or 0) for f in FIELDS}
    return bool(_eval(tree, env))
