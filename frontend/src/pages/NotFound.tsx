import { Link } from "react-router-dom";
import { EmptyState } from "@/components/EmptyState";

export function NotFound() {
  return (
    <div className="card">
      <EmptyState
        glyph="∅"
        title="Page not found"
        description="The screen you requested does not exist."
        action={<Link to="/">Back to Mainboard</Link>}
      />
    </div>
  );
}
