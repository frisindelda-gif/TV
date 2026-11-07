import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { CareerProvider } from "./lib/career";
import { EvaluationProvider } from "./lib/evaluation";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <CareerProvider>
        <EvaluationProvider>
          <App />
        </EvaluationProvider>
      </CareerProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
