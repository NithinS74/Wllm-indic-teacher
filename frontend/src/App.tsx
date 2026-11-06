import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { ToastProvider } from "@/components/ui/toast";
import { DashboardPage } from "@/pages/DashboardPage";
import { NewLecturePage } from "@/pages/NewLecturePage";
import { ProcessingPage } from "@/pages/ProcessingPage";
import { LectureWorkspacePage } from "@/pages/LectureWorkspacePage";
import { MyLecturesPage } from "@/pages/MyLecturesPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AboutPage } from "@/pages/AboutPage";
import { Button } from "@/components/ui/button";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 2000,
    },
  },
});

function NotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <p className="text-4xl font-semibold text-zinc-300">404</p>
      <p className="mt-3 text-sm text-zinc-600">Page not found.</p>
      <Button className="mt-5" asChild>
        <a href="/">Back to dashboard</a>
      </Button>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <AppShell>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/new" element={<NewLecturePage />} />
              <Route path="/lectures" element={<MyLecturesPage />} />
              <Route path="/lectures/:id" element={<LectureWorkspacePage />} />
              <Route path="/processing/:jobId" element={<ProcessingPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/index.html" element={<Navigate to="/" replace />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AppShell>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
