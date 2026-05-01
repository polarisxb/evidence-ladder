import { request } from "./client";
import type { BuiltinTarget } from "../types";

export async function listBuiltinTargets(): Promise<BuiltinTarget[]> {
  const res = await request<{ data: BuiltinTarget[] }>("/targets/builtin");
  return res.data;
}
