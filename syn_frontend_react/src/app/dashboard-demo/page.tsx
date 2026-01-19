"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Activity, CreditCard, DollarSign, Users, ArrowUpRight, Search, Filter, Sparkles } from "lucide-react"
import { SpotlightCard } from "@/components/ui/sci-fi/spotlight-card"
import { BorderBeam } from "@/components/ui/sci-fi/border-beam"
import { ShimmerButton } from "@/components/ui/sci-fi/shimmer-button"
import { ButtonMovingBorder } from "@/components/ui/sci-fi/moving-border"

export default function DashboardDemoPage() {
    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-white bg-clip-text text-transparent bg-gradient-to-r from-white to-white/50">
                        Sci-Fi Dashboard
                    </h2>
                    <p className="text-muted-foreground">
                        Next-generation interface with advanced motion and lighting.
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <ButtonMovingBorder>
                        <Sparkles className="mr-2 h-4 w-4 text-white" />
                        AI Analysis
                    </ButtonMovingBorder>
                    <ShimmerButton className="shadow-2xl">
                        <span className="whitespace-pre-wrap text-center text-sm font-medium leading-none tracking-tight text-white dark:from-white dark:to-slate-900/10 lg:text-lg">
                            Generate Report
                        </span>
                    </ShimmerButton>
                </div>
            </div>

            {/* Stats Cards with Spotlight */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <SpotlightCard>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Total Revenue
                        </CardTitle>
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">$45,231.89</div>
                        <p className="text-xs text-muted-foreground">
                            <span className="text-emerald-500 flex items-center gap-1 inline-flex">
                                +20.1% <ArrowUpRight className="h-3 w-3" />
                            </span>{" "}
                            from last month
                        </p>
                    </CardContent>
                </SpotlightCard>
                <SpotlightCard spotlightColor="rgba(255, 255, 255, 0.2)">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Subscriptions
                        </CardTitle>
                        <Users className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">+2350</div>
                        <p className="text-xs text-muted-foreground">
                            <span className="text-emerald-500 flex items-center gap-1 inline-flex">
                                +180.1% <ArrowUpRight className="h-3 w-3" />
                            </span>{" "}
                            from last month
                        </p>
                    </CardContent>
                </SpotlightCard>
                <SpotlightCard spotlightColor="rgba(255, 255, 255, 0.2)">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Sales
                        </CardTitle>
                        <CreditCard className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">+12,234</div>
                        <p className="text-xs text-muted-foreground">
                            <span className="text-emerald-500 flex items-center gap-1 inline-flex">
                                +19% <ArrowUpRight className="h-3 w-3" />
                            </span>{" "}
                            from last month
                        </p>
                    </CardContent>
                </SpotlightCard>
                <SpotlightCard>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground">
                            Active Now
                        </CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-white">+573</div>
                        <p className="text-xs text-muted-foreground">
                            <span className="text-emerald-500 flex items-center gap-1 inline-flex">
                                +201 <ArrowUpRight className="h-3 w-3" />
                            </span>{" "}
                            since last hour
                        </p>
                    </CardContent>
                </SpotlightCard>
            </div>

            {/* Main Content Tabs */}
            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="analytics">Analytics</TabsTrigger>
                    <TabsTrigger value="reports">Reports</TabsTrigger>
                    <TabsTrigger value="notifications">Notifications</TabsTrigger>
                </TabsList>
                <TabsContent value="overview" className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                        <div className="col-span-4 relative rounded-xl border border-white/10 bg-black/40 backdrop-blur-xl">
                            <BorderBeam size={250} duration={12} delay={9} />
                            <CardHeader>
                                <CardTitle>Recent Sales</CardTitle>
                                <CardDescription>
                                    You made 265 sales this month.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-8">
                                    {/* Mock Chart Placeholder */}
                                    <div className="h-[200px] w-full rounded-md bg-white/5 flex items-center justify-center text-muted-foreground text-sm border border-white/5">
                                        [Chart Component Placeholder]
                                    </div>
                                </div>
                            </CardContent>
                        </div>
                        <Card className="col-span-3">
                            <CardHeader>
                                <CardTitle>Recent Activity</CardTitle>
                                <CardDescription>
                                    Latest system events and logs.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-8">
                                    {[1, 2, 3, 4, 5].map((i) => (
                                        <div key={i} className="flex items-center">
                                            <div className="h-9 w-9 rounded-full bg-white/10 border border-white/10 flex items-center justify-center text-white shadow-glow-white">
                                                <Activity className="h-4 w-4" />
                                            </div>
                                            <div className="ml-4 space-y-1">
                                                <p className="text-sm font-medium leading-none text-white">
                                                    New user registered
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    User #{1000 + i} joined the platform
                                                </p>
                                            </div>
                                            <div className="ml-auto font-medium text-xs text-muted-foreground">
                                                {i}h ago
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Table Section */}
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between">
                            <div>
                                <CardTitle>Transactions</CardTitle>
                                <CardDescription>
                                    Recent transactions from your store.
                                </CardDescription>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input placeholder="Search..." className="pl-8 w-[200px]" />
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[100px]">Invoice</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Method</TableHead>
                                        <TableHead className="text-right">Amount</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {[
                                        { id: "INV001", status: "Paid", method: "Credit Card", amount: "$250.00" },
                                        { id: "INV002", status: "Pending", method: "PayPal", amount: "$150.00" },
                                        { id: "INV003", status: "Unpaid", method: "Bank Transfer", amount: "$350.00" },
                                        { id: "INV004", status: "Paid", method: "Credit Card", amount: "$450.00" },
                                        { id: "INV005", status: "Paid", method: "PayPal", amount: "$550.00" },
                                    ].map((invoice) => (
                                        <TableRow key={invoice.id}>
                                            <TableCell className="font-medium text-white">{invoice.id}</TableCell>
                                            <TableCell>
                                                <Badge variant={invoice.status === "Paid" ? "default" : invoice.status === "Pending" ? "secondary" : "destructive"}>
                                                    {invoice.status}
                                                </Badge>
                                            </TableCell>
                                            <TableCell>{invoice.method}</TableCell>
                                            <TableCell className="text-right text-white">{invoice.amount}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    )
}

