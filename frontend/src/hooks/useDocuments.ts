import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type DocumentInfo } from "../lib/api";

const key = ["documents"] as const;

export function useDocuments() {
  return useQuery({
    queryKey: key,
    queryFn: api.documents,
    // Poll while anything is still being read, then stop.
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === "processing") ? 1000 : false),
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.upload,
    onSuccess: (doc) => qc.setQueryData<DocumentInfo[]>(key, (old = []) => [doc, ...old]),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.remove,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<DocumentInfo[]>(key);
      qc.setQueryData<DocumentInfo[]>(key, (old = []) => old.filter((d) => d.id !== id));
      return { previous };
    },
    onError: (_err, _id, ctx) => qc.setQueryData(key, ctx?.previous),
  });
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: Infinity, retry: 1 });
}
