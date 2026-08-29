import aws_cdk as cdk
from config import DeployConfig
from stacks.api_stack import ApiStack
from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack
from stacks.observability_stack import ObservabilityStack

app = cdk.App()
config = DeployConfig.from_app(app)
shared = {"config": config, "env": config.env, "synthesizer": config.synthesizer}

foundation = FoundationStack(app, config.stack("foundation"), **shared)
messaging = MessagingStack(app, config.stack("messaging"), **shared)
api = ApiStack(
    app, config.stack("api"), foundation=foundation, messaging=messaging, **shared
)
ObservabilityStack(
    app, config.stack("observability"), api=api, messaging=messaging, **shared
)

cdk.Tags.of(app).add("project", config.project)
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
