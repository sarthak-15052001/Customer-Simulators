import {
  useMutation,
  type UseMutationOptions,
} from "@tanstack/react-query";

import familyApi, {
  type FamilyQfInput,
  type FamilyQfOutput,
} from "../api/family.api";

export function useFamilyQfMutation(
  options?: Pick<
    UseMutationOptions<FamilyQfOutput, Error, FamilyQfInput>,
    "onSuccess" | "onError"
  >,
) {
  return useMutation({
    mutationFn: (input: FamilyQfInput) => familyApi.postFamilyQf(input),
    ...options,
  });
}
