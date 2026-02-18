import { ecsAwsAccessKeyId, ecsAwsSecretAccessKey, ecsClusterName, ecsContainerName, ecsRegion, ecsRunnerTaskDefinition, ecsSecurityGroup, ecsSubnets } from "../config/config";

const config = {
  aws: {
    ecs: {
      clusterName: ecsClusterName,
      runnerTaskDefinition: ecsRunnerTaskDefinition,
      subnets: ecsSubnets,
      securityGroup: ecsSecurityGroup,
      containerName: ecsContainerName,
    },
    region: ecsRegion,
    accessKeyId: ecsAwsAccessKeyId,
    secretAccessKey: ecsAwsSecretAccessKey,
  },
};

export default config;
