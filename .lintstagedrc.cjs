module.exports = {
  "syn_frontend_react/**/*.{js,jsx,ts,tsx}": (files) => {
    const rel = files
      .map((file) => file.replace(/\\/g, "/"))
      .map((file) => file.replace(/^syn_frontend_react\//, ""));

    if (rel.length === 0) return [];

    const quoted = rel.map((file) => JSON.stringify(file)).join(" ");
    return [`npx --prefix syn_frontend_react eslint --fix -- ${quoted}`];
  },
};
