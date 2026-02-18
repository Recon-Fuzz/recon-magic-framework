import axios from "axios";
import { fetchMonitoringsForOrg } from "../db/monitorings";

export async function fetchMonitoringsForOrgWithData(organizationId: string) {
  const foundMonitorings = await fetchMonitoringsForOrg(organizationId);

  // Given each monitoring
  const resultsToSend = await Promise.all(
    foundMonitorings.map(async (monitoring) => {
      try {
        const res = await axios({
          method: "GET",
          url: monitoring.service?.url,
          data: monitoring.serviceParams
            ? JSON.parse(monitoring?.serviceParams as string)
            : undefined,
          headers: {
            Authorization: monitoring.service?.authorizationSecret
              ? monitoring.service?.authorizationSecret
              : undefined,
          },
        });
        return {
          id: monitoring.id,
          data: res.data,
          status: 200,
        };
      } catch (e: any) {
        if (e?.response?.data) {
          return {
            data: e?.response?.data,
            status: e?.response?.status,
          };
        } else {
          return {
            id: monitoring.id,
            data: {},
            status: 500,
          };
        }
      }
    })
  );

  return resultsToSend;
}
