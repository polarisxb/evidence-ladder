import { request } from "./client";
import type { BuiltinTarget, MockTarget } from "../types";

export async function listBuiltinTargets(): Promise<BuiltinTarget[]> {
  const res = await request<{ data: BuiltinTarget[] }>("/targets/builtin");
  return res.data;
}

export async function listMockTargets(): Promise<MockTarget[]> {
  const res = await request<{ data: MockTarget[] }>("/targets/mock");
  return res.data;
}
