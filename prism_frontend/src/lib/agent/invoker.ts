export async function invoke(
  command: "list_scripts" | "run_script",
  args?: Record<string, any>
) {
  const url =
    command === "list_scripts"
      ? "/api/ai/scripts/list"
      : "/api/ai/scripts/run";

  const payload =
    command === "list_scripts"
      ? undefined
      : {
          name: args?.name,
          args: args?.args ?? [],
        };

  const response = await fetch(url, {
    method: command === "list_scripts" ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: command === "list_scripts" ? undefined : JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error?.message || `Request failed with status ${response.status}`
    );
  }

  const data = await response.json();
  if (data.status !== "success") {
    throw new Error(data.message || "Unknown error");
  }
  return data.result || data.scripts || data;
}

