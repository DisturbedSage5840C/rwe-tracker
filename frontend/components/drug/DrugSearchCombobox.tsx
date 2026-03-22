"use client";

import { useRef, useState } from "react";
import useSWR from "swr";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { toast } from "sonner";

import { api, type DrugRead } from "@/lib/api";
import { useAuthStore } from "@/lib/store/auth-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const newDrugSchema = z.object({
  name: z.string().min(1, "Drug name is required"),
  indication: z.string().optional(),
  manufacturer: z.string().optional(),
});

type NewDrugValues = z.infer<typeof newDrugSchema>;

export function DrugSearchCombobox({
  value,
  onChange,
}: {
  value: string;
  onChange: (drug: DrugRead) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const timer = useRef<number | null>(null);
  const token = useAuthStore((state) => state.accessToken);

  const form = useForm<NewDrugValues>({
    resolver: zodResolver(newDrugSchema),
    defaultValues: { name: "", indication: "", manufacturer: "" },
  });

  const { data, mutate } = useSWR(
    token ? ["drug-search", debouncedQuery, token] : null,
    async () => {
      api.setAccessToken(token);
      const response = await api.listDrugs({ limit: 20, search: debouncedQuery });
      return response.data.items;
    },
    { keepPreviousData: true, revalidateOnFocus: false },
  );

  const drugs = data ?? [];

  const onSearchChange = (text: string) => {
    setQuery(text);
    if (timer.current) {
      window.clearTimeout(timer.current);
    }
    timer.current = window.setTimeout(() => {
      setDebouncedQuery(text);
    }, 300);
  };

  const onCreateDrug = form.handleSubmit(async (values) => {
    if (!token) {
      toast.error("Please sign in to create a monitored drug");
      return;
    }
    setIsCreating(true);
    try {
      api.setAccessToken(token);
      const created = await api.createDrug({
        name: values.name,
        indication: values.indication ?? null,
        manufacturer: values.manufacturer ?? null,
      });
      await mutate();
      onChange(created.data);
      setCreateOpen(false);
      form.reset();
      toast.success("Drug created successfully");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to create drug");
    } finally {
      setIsCreating(false);
    }
  });

  return (
    <div className="flex items-center gap-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            aria-label="Select drug"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-[360px] justify-between"
          >
            {value || "Search drug..."}
            <ChevronsUpDown className="ml-2 h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[420px] p-0" align="start">
          <Command>
            <CommandInput aria-label="Search drugs" placeholder="Search by drug name" value={query} onValueChange={onSearchChange} />
            <CommandList>
              <CommandEmpty>No matching drugs.</CommandEmpty>
              <CommandGroup heading="Drugs">
                {drugs.map((drug) => (
                  <CommandItem
                    key={drug.id}
                    value={drug.name}
                    onSelect={() => {
                      onChange(drug);
                      setOpen(false);
                    }}
                    aria-label={`Select ${drug.name}`}
                  >
                    <Check className={cn("h-4 w-4", value === drug.name ? "opacity-100" : "opacity-0")} />
                    <div className="flex flex-col">
                      <span>{drug.name}</span>
                      <span className="text-[12px] text-slate-500">
                        {(drug.indication && drug.indication.trim()) || "Therapeutic area unavailable"}
                        {" • "}
                        {(drug.manufacturer && drug.manufacturer.trim()) || "Unknown manufacturer"}
                        {" • "}
                        {new Date(drug.created_at).toLocaleString()}
                      </span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogTrigger asChild>
          <Button aria-label="Add new drug" variant="secondary">
            <Plus className="mr-1 h-4 w-4" /> Add new drug
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create monitored drug</DialogTitle>
            <DialogDescription>Enter baseline metadata for the drug you want to track.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form className="space-y-4" onSubmit={onCreateDrug}>
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Drug name</FormLabel>
                    <FormControl>
                      <Input aria-label="Drug name" placeholder="Enter drug name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="indication"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Therapeutic area</FormLabel>
                    <FormControl>
                      <Input aria-label="Therapeutic area" placeholder="Oncology" {...field} value={field.value ?? ""} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="manufacturer"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Manufacturer</FormLabel>
                    <FormControl>
                      <Input aria-label="Manufacturer" placeholder="Company name" {...field} value={field.value ?? ""} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button aria-label="Create drug" type="submit" disabled={isCreating}>
                  {isCreating ? "Creating..." : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
