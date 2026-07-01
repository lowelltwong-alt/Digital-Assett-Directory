route = {
    "id": "dad:asset:example",
    "repo": "target",
    "human": "maybe",
}

route["repo"] = 42

print(route["id"] + "->" + str(route["repo"]))
