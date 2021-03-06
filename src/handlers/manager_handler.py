"""
  Copyright 2018-2020 National Geographic Society

  Use of this software does not constitute endorsement by National Geographic
  Society (NGS). The NGS name and NGS logo may not be used for any purpose without
  written permission from NGS.

  Licensed under the Apache License, Version 2.0 (the "License"); you may not use
  this file except in compliance with the License. You may obtain a copy of the
  License at

      https://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software distributed
  under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
  CONDITIONS OF ANY KIND, either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
"""

import json
import os

import boto3
import sentry_sdk
import sys
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import MetricHandler  # noqa
from helpers.logging import get_logger  # noqa
from helpers.util import required_keys  # noqa

sns = boto3.client("sns")

SENTRY_DSN = os.environ["SENTRY_DSN"]
SNS_WORKER_TOPIC_ARN = os.environ["SNS_WORKER_TOPIC_ARN"]

sentry_sdk.init(dsn=SENTRY_DSN, integrations=[AwsLambdaIntegration()])  # AWS Lambda integration

logger = get_logger("manager-handler")


def lambda_handler(event, context):
    """
    :param event:  AWS Lambda uses this parameter to pass in event data to the handler.
        For details, see: https://docs.aws.amazon.com/lambda/latest/dg/with-sns.html
    :param context: AWS Lambda uses this parameter to provide runtime information to your handler.
        For details, see: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    :return:
    """
    logger.debug(f"Received event: {event['Records'][0]['Sns']['MessageId']}")

    message = event["Records"][0]["Sns"]["Message"]
    decoded = json.loads(message)

    required_keys(decoded, ["id", "version"])

    resource_id, version = decoded["id"], decoded["version"]

    logger.debug(f"Handling event for resource: {resource_id} and version: {version}")

    if "resources" in decoded and len(decoded["resources"]):
        compute_resources = [
            r for r in decoded["resources"] if MetricHandler.has_slug(r)  # filter by slug name;
        ]
    else:
        compute_resources = MetricHandler.slugs()  # all handlers;

    # splitting the workflow into multiple workers, each worker should handle a single metric computation.
    for handler in compute_resources:
        logger.debug(f"Sending compute event for: {handler} and resource: {resource_id}")

        decoded["meta"] = {"worker": {"handler": handler}}
        sns.publish(TopicArn=SNS_WORKER_TOPIC_ARN, Message=json.dumps(decoded))

    logger.debug(f"Successfully handled event for resource: {resource_id} and version: {version}")
