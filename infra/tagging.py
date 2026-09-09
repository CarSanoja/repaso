import aws_cdk as cdk
import jsii
from constructs import IConstruct

CUSTOM_PREFIX = "Custom::"
CUSTOM_TYPE = "AWS::CloudFormation::CustomResource"

TAG_PROPERTY = {"AWS::Budgets::Budget": "ResourceTags"}

UNTAGGABLE = frozenset(
    {
        "AWS::ApiGatewayV2::Integration",
        "AWS::ApiGatewayV2::Route",
        "AWS::Bedrock::GuardrailVersion",
        "AWS::IAM::Policy",
        "AWS::KMS::Alias",
        "AWS::Lambda::Permission",
        "AWS::S3::BucketPolicy",
        "AWS::SNS::Subscription",
        "AWS::SQS::QueuePolicy",
    }
)


def _manages_own_tags(node: cdk.CfnResource) -> bool:
    return cdk.TagManager.is_taggable(node) or cdk.TagManager.is_taggable_v2(node)


def carries_no_tags(resource_type: str) -> bool:
    if resource_type in UNTAGGABLE:
        return True
    return resource_type.startswith(CUSTOM_PREFIX) or resource_type == CUSTOM_TYPE


@jsii.implements(cdk.IAspect)
class TagEveryResource:
    def __init__(self, tags: dict[str, str]) -> None:
        self.entries = [{"Key": key, "Value": value} for key, value in sorted(tags.items())]

    def visit(self, node: IConstruct) -> None:
        if not isinstance(node, cdk.CfnResource):
            return
        resource_type = node.cfn_resource_type
        if carries_no_tags(resource_type):
            return
        override = TAG_PROPERTY.get(resource_type)
        if override is None and _manages_own_tags(node):
            return
        node.add_property_override(override or "Tags", self.entries)
