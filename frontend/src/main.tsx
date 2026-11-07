import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { CareerProvider } from "./lib/career";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <CareerProvider>
        <App />
      </CareerProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
