import aws_cdk as cdk
from config import DeployConfig
from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

app = cdk.App()
config = DeployConfig.from_app(app)

FoundationStack(app, config.stack("foundation"), config=config, env=config.env)
MessagingStack(app, config.stack("messaging"), config=config, env=config.env)

cdk.Tags.of(app).add("project", config.project)
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
