"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth-store";

const loginSchema = z.object({
  email: z.string().email("Enter a valid enterprise email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const email = params.get("email");
    const expired = params.get("expired");
    if (email) {
      form.reset({
        email: email ?? "",
        password: "",
      });

      const scrubbedParams = new URLSearchParams(window.location.search);
      scrubbedParams.delete("email");
      scrubbedParams.delete("password");
      const scrubbedQuery = scrubbedParams.toString();
      const scrubbedUrl = `${window.location.pathname}${scrubbedQuery ? `?${scrubbedQuery}` : ""}`;
      window.history.replaceState({}, "", scrubbedUrl);
    }
    if (expired === "1") {
      toast.error("Session expired. Please sign in again.");
    }
  }, [form]);

  const onSubmit = form.handleSubmit(async (values) => {
    setIsSubmitting(true);
    try {
      const tokenResponse = await api.login(values);
      api.setAccessToken(tokenResponse.data.access_token);

      const sessionResponse = await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken: tokenResponse.data.refresh_token }),
      });

      if (!sessionResponse.ok) {
        throw new Error("Unable to initialize secure session");
      }

      const me = await api.me();
      setAuth({
        user: me.data,
        org: null,
        accessToken: tokenResponse.data.access_token,
      });

      router.push("/dashboard");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }, () => {
    toast.error("Enter a valid email and password to continue");
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>RWE Tracker Sign In</CardTitle>
          <CardDescription>Authenticate with your medical-affairs workspace credentials.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={onSubmit} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input aria-label="Email" type="email" autoComplete="email" placeholder="name@company.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input aria-label="Password" type="password" autoComplete="current-password" placeholder="••••••••" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button aria-label="Sign in" type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Continue
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </main>
  );
}
