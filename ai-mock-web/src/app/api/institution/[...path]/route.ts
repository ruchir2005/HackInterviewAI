import { auth } from "@/auth";
import { API_BASE } from "@/app/lib/api";
import { NextRequest, NextResponse } from "next/server";

const INSTITUTION_PROXY_SECRET =
  process.env.INSTITUTION_PROXY_SECRET || process.env.ADMIN_PROXY_SECRET;

type Context = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: Context) {
  const session = await auth();
  const email = session?.user?.email;
  if (!email) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  if (!INSTITUTION_PROXY_SECRET) {
    return NextResponse.json(
      { detail: "Institution API is not configured" },
      { status: 500 }
    );
  }

  const { path } = await context.params;
  const safePath = path.map(encodeURIComponent).join("/");
  const query = request.nextUrl.searchParams.toString();
  const url = `${API_BASE}/api/institution/${safePath}${query ? `?${query}` : ""}`;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const body = hasBody ? await request.text() : undefined;

  try {
    const response = await fetch(url, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Institution-Secret": INSTITUTION_PROXY_SECRET,
        "X-Verified-User-Email": email,
        "X-Verified-User-Name": encodeURIComponent(session.user.name || ""),
      },
      body: body || undefined,
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text || null, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Institution service is unavailable" },
      { status: 502 }
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
