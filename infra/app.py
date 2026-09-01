import os
from pathlib import Path

import aws_cdk as cdk
from config import DeployConfig
from stacks.agentcore_stack import AgentCoreStack
from stacks.api_stack import ApiStack
from stacks.foundation_stack import FoundationStack
from stacks.guardrails_stack import GuardrailsStack
from stacks.messaging_stack import MessagingStack
from stacks.observability_stack import ObservabilityStack

DEFAULT_OUTDIR = str(Path(__file__).resolve().parent / "cdk.out")

app = cdk.App(outdir=os.environ.get("CDK_OUTDIR") or DEFAULT_OUTDIR)
config = DeployConfig.from_app(app)
shared = {"config": config, "env": config.env, "synthesizer": config.synthesizer}

foundation = FoundationStack(app, config.stack("foundation"), **shared)
messaging = MessagingStack(app, config.stack("messaging"), **shared)
guardrails = GuardrailsStack(app, config.stack("guardrails"), **shared)
api = ApiStack(
    app, config.stack("api"), foundation=foundation, messaging=messaging, **shared
)
AgentCoreStack(
    app,
    config.stack("agentcore"),
    foundation=foundation,
    messaging=messaging,
    guardrails=guardrails,
    **shared,
)
ObservabilityStack(
    app, config.stack("observability"), api=api, messaging=messaging, **shared
)

cdk.Tags.of(app).add("project", config.project)
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
