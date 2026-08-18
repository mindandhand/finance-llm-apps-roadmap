from cube import config


@config("context_to_groups")
def context_to_groups(ctx: dict) -> list[str]:
    return ctx.get("securityContext", {}).get("groups", [])
