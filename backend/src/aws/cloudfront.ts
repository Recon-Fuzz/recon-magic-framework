import { getSignedUrl as _getSignedUrl } from "@aws-sdk/cloudfront-signer";
import { assetsUrl, awsCloudFrondKeyPairId, awsCloudFrontPrivateKey } from "../config/config";

export function getSignedUrl(key: string, expiresIn = 60 * 60 * 1000) {
  const dateLessThan = new Date()
  dateLessThan.setTime(dateLessThan.getTime() + expiresIn);
  const url = _getSignedUrl({
    url: `${assetsUrl}${key}`,
    keyPairId: awsCloudFrondKeyPairId,
    dateLessThan: dateLessThan.toString(),
    privateKey: awsCloudFrontPrivateKey,
  });
  return url;
}
