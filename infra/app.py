import aws_cdk as cdk
from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

app = cdk.App()
env = cdk.Environment(region="us-east-1")

foundation = FoundationStack(app, "repaso-foundation", env=env)
MessagingStack(app, "repaso-messaging", env=env)

cdk.Tags.of(app).add("project", "repaso")
cdk.Tags.of(app).add("managed-by", "cdk")

app.synth()
