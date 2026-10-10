import { auth } from "./auth";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware to protect routes that require authentication.
 * Redirects unauthenticated users to the login page.
 */
export default async function middleware(req: NextRequest) {
    const session = await auth();
    const { nextUrl } = req;
    const isLoggedIn = !!session?.user;

    // Define protected routes that require authentication
    const protectedRoutes = [
        "/resume",
        "/resume-analyzer",
        "/hr-interview",
        "/Interview",
        "/InterviewSelectionPage",
        "/assessment",
        "/dashboard",
        "/institution",
    ];

    // Check if the current path starts with any protected route
    const isProtectedRoute = protectedRoutes.some(
        (route) => nextUrl.pathname === route || nextUrl.pathname.startsWith(`${route}/`)
    );

    // If trying to access a protected route without being logged in
    if (isProtectedRoute && !isLoggedIn) {
        // Store the original URL to redirect back after login
        const callbackUrl = encodeURIComponent(nextUrl.pathname + nextUrl.search);
        return NextResponse.redirect(
            new URL(`/login?callbackUrl=${callbackUrl}`, nextUrl.origin)
        );
    }

    // If logged in and trying to access login/signup, redirect to resume
    if (isLoggedIn && (nextUrl.pathname === "/login" || nextUrl.pathname === "/signup")) {
        return NextResponse.redirect(new URL("/resume", nextUrl.origin));
    }

    return NextResponse.next();
}

// Configure which routes the middleware should run on
export const config = {
    matcher: [
        /*
         * Match all request paths except:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         * - public folder
         */
        "/((?!api|_next/static|_next/image|favicon.ico|public).*)",
    ],
};
