// Minimal static server for the built React app — used by cPanel "Setup Node.js App".
// It serves the ./build folder and sends index.html for client-side routes (SPA).
const path = require("path");
const express = require("express");

const app = express();
const buildDir = path.join(__dirname, "build");

app.use(express.static(buildDir));

// SPA fallback: any non-file route returns index.html
app.get("*", (req, res) => {
  res.sendFile(path.join(buildDir, "index.html"));
});

// cPanel/Passenger provides PORT via env
const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`PROPTO frontend running on port ${port}`));
