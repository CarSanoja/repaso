OWN = "<own>"
ACCOUNT = "<account>"
FOREIGN_IMPORT = "<import:"

PSEUDO = {
    "AWS::AccountId": ACCOUNT,
    "AWS::Region": "<region>",
    "AWS::Partition": "aws",
    "AWS::URLSuffix": "amazonaws.com",
    "AWS::StackName": "<stack>",
    "AWS::StackId": "<stack>",
    "AWS::NoValue": "",
}

CALLS = ("Ref", "Fn::GetAtt", "Fn::ImportValue", "Fn::Join", "Fn::Sub", "Fn::Select", "Fn::If")


def is_call(node: object) -> bool:
    return isinstance(node, dict) and len(node) == 1 and next(iter(node)) in CALLS


def collapse(node: object, owner: str) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(collapse(item, owner) for item in node)
    if not isinstance(node, dict):
        return "" if node is None else str(node)
    if not is_call(node):
        return "".join(collapse(value, owner) for value in node.values())
    name, argument = next(iter(node.items()))
    return _call(name, argument, owner)


def _call(name: str, argument: object, owner: str) -> str:
    if name == "Ref":
        return PSEUDO.get(str(argument), OWN)
    if name == "Fn::GetAtt":
        return OWN
    if name == "Fn::ImportValue":
        exported = collapse(argument, owner)
        return OWN if exported.startswith(f"{owner}-") else f"{FOREIGN_IMPORT}{exported}>"
    if name == "Fn::Join" and isinstance(argument, list):
        return collapse(argument[0], owner).join(collapse(part, owner) for part in argument[1])
    if name == "Fn::Sub":
        return _substitute(argument, owner)
    if name in ("Fn::Select", "Fn::If") and isinstance(argument, list):
        return "".join(collapse(part, owner) for part in argument[1:])
    return collapse(argument, owner)


def _substitute(argument: object, owner: str) -> str:
    template = argument[0] if isinstance(argument, list) else argument
    text = collapse(template, owner)
    for pseudo, value in PSEUDO.items():
        text = text.replace("${" + pseudo + "}", value)
    while "${" in text:
        start = text.index("${")
        end = text.find("}", start)
        if end < 0:
            break
        text = text[:start] + OWN + text[end + 1 :]
    return text
