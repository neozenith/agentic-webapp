import { BarChart3, MessagesSquare, Wrench } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";

export function Home() {
  return (
    <Card className="animate-fade-in-up">
      <CardHeader>
        <h1 className="text-2xl font-semibold leading-none">agentic-webapp</h1>
        <CardDescription className="text-base leading-relaxed">
          A scale-to-zero Cloud Run app: an async FastAPI backend serving this React UI, with a Google ADK agent running
          as a sidecar. Every LLM call is itemised (tokens + estimated cost) into BigQuery.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        <Button asChild>
          <Link to="/chat">
            <MessagesSquare /> Chat with the agent
          </Link>
        </Button>
        <Button asChild variant="secondary">
          <Link to="/admin">
            <BarChart3 /> Usage &amp; billing
          </Link>
        </Button>
        <Button asChild variant="outline">
          <a href="/dev-ui/" target="_blank" rel="noreferrer">
            <Wrench /> ADK debug UI
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}
