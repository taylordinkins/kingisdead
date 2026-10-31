import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Typed API client; `/api` is proxied to the FastAPI server in dev. */
export const api = createClient<paths>({ baseUrl: "/" });
