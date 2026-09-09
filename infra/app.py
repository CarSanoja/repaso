import os
from pathlib import Path

import aws_cdk as cdk
from config import DeployConfig
from namespace_guard import enforce_assembly
from stacks.agentcore_stack import AgentCoreStack
from stacks.api_stack import ApiStack
from stacks.foundation_stack import FoundationStack
from stacks.guardrails_stack import GuardrailsStack
from stacks.messaging_stack import MessagingStack
from stacks.observability_stack import ObservabilityStack
from tagging import TagEveryResource

DEFAULT_OUTDIR = str(Path(__file__).resolve().parent / "cdk.out")
MODE_OUTPUT = "DeploymentMode"

app = cdk.App(outdir=os.environ.get("CDK_OUTDIR") or DEFAULT_OUTDIR)
config = DeployConfig.from_app(app)
shared = {"config": config, "env": config.env, "synthesizer": config.synthesizer}

foundation = FoundationStack(app, config.stack("foundation"), **shared)
messaging = MessagingStack(app, config.stack("messaging"), **shared)
guardrails = GuardrailsStack(app, config.stack("guardrails"), **shared)
api = ApiStack(app, config.stack("api"), foundation=foundation, messaging=messaging, **shared)
agentcore = AgentCoreStack(
    app,
    config.stack("agentcore"),
    foundation=foundation,
    messaging=messaging,
    guardrails=guardrails,
    api=api,
    **shared,
)
observability = ObservabilityStack(
    app, config.stack("observability"), api=api, messaging=messaging, **shared
)

for stack in (foundation, messaging, guardrails, api, agentcore, observability):
    cdk.CfnOutput(stack, MODE_OUTPUT, value=config.mode.value)

for tag, value in config.tags.items():
    cdk.Tags.of(app).add(tag, value)
cdk.Aspects.of(app).add(TagEveryResource(config.tags))

enforce_assembly(app.synth(), config.project, config.bootstrap_qualifier)
