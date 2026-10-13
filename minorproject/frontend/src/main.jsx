import { MotionConfig } from "motion/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { FeedProvider } from "./hooks/useFeed";
import "./index.css";
import Archive from "./pages/Archive";
import LiveDesk from "./pages/LiveDesk";
import Method from "./pages/Method";
import RunView from "./pages/RunView";
import Studio from "./pages/Studio";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <FeedProvider>
          <Layout>
            <Routes>
              <Route path="/" element={<Studio />} />
              <Route path="/runs/:id" element={<RunView />} />
              <Route path="/live" element={<LiveDesk />} />
              <Route path="/archive" element={<Archive />} />
              <Route path="/method" element={<Method />} />
            </Routes>
          </Layout>
        </FeedProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>
);
