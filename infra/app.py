import aws_cdk as cdk
from config import DeployConfig
from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

app = cdk.App()
config = DeployConfig.from_app(app)
shared = {"config": config, "env": config.env, "synthesizer": config.synthesizer}

FoundationStack(app, config.stack("foundation"), **shared)
MessagingStack(app, config.stack("messaging"), **shared)

cdk.Tags.of(app).add("project", config.project)
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
