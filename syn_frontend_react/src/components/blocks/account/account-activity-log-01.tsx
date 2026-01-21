"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Activity,
  LogIn,
  Settings,
  Shield,
  Key,
  Mail,
  Globe,
  Smartphone,
  Monitor,
  AlertCircle,
  CheckCircle
} from "lucide-react";
import { useState } from "react";

interface ActivityEvent {
  id: string;
  type: "security" | "settings" | "login" | "api" | "content";
  action: string;
  description: string;
  timestamp: string;
  ipAddress: string;
  location: string;
  device: string;
  success: boolean;
  critical?: boolean;
}

const activityEvents: ActivityEvent[] = [
  {
    id: "1",
    type: "login",
    action: "Successful login",
    description: "Signed in from Chrome on MacBook Pro",
    timestamp: "2 hours ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "MacBook Pro",
    success: true,
  },
  {
    id: "2",
    type: "settings",
    action: "Updated notification preferences",
    description: "Changed email notification settings",
    timestamp: "5 hours ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "MacBook Pro",
    success: true,
  },
  {
    id: "3",
    type: "security",
    action: "Password changed",
    description: "Account password was successfully updated",
    timestamp: "1 day ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "MacBook Pro",
    success: true,
    critical: true,
  },
  {
    id: "4",
    type: "api",
    action: "API key created",
    description: "New API key 'Production API' generated",
    timestamp: "2 days ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "MacBook Pro",
    success: true,
  },
  {
    id: "5",
    type: "login",
    action: "Failed login attempt",
    description: "Login failed - incorrect password",
    timestamp: "3 days ago",
    ipAddress: "203.0.113.0",
    location: "London, UK",
    device: "Unknown",
    success: false,
    critical: true,
  },
  {
    id: "6",
    type: "security",
    action: "2FA enabled",
    description: "Two-factor authentication was enabled",
    timestamp: "5 days ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "iPhone 14",
    success: true,
    critical: true,
  },
  {
    id: "7",
    type: "settings",
    action: "Profile updated",
    description: "Changed profile picture and bio",
    timestamp: "1 week ago",
    ipAddress: "192.168.1.1",
    location: "New York, USA",
    device: "MacBook Pro",
    success: true,
  },
  {
    id: "8",
    type: "login",
    action: "Successful login",
    description: "Signed in from Safari on iPhone",
    timestamp: "1 week ago",
    ipAddress: "192.168.1.2",
    location: "New York, USA",
    device: "iPhone 14",
    success: true,
  },
];

export const title = "Account Activity Log";

export default function AccountActivityLog01() {
  const [filterType, setFilterType] = useState<string>("all");

  const filteredEvents = activityEvents.filter((event) =>
    filterType === "all" ? true : event.type === filterType
  );

  const getEventIcon = (type: string) => {
    switch (type) {
      case "login":
        return <LogIn className="h-4 w-4" />;
      case "security":
        return <Shield className="h-4 w-4" />;
      case "settings":
        return <Settings className="h-4 w-4" />;
      case "api":
        return <Key className="h-4 w-4" />;
      case "content":
        return <Mail className="h-4 w-4" />;
      default:
        return <Activity className="h-4 w-4" />;
    }
  };

  const getEventBadge = (type: string) => {
    switch (type) {
      case "login":
        return <Badge variant="outline" className="border-blue-200 text-blue-700">Login</Badge>;
      case "security":
        return <Badge variant="outline" className="border-red-200 text-red-700">Security</Badge>;
      case "settings":
        return <Badge variant="outline" className="border-green-200 text-green-700">Settings</Badge>;
      case "api":
        return <Badge variant="outline" className="border-purple-200 text-purple-700">API</Badge>;
      case "content":
        return <Badge variant="outline" className="border-orange-200 text-orange-700">Content</Badge>;
      default:
        return <Badge variant="outline">Other</Badge>;
    }
  };

  const getDeviceIcon = (device: string) => {
    if (device.includes("iPhone") || device.includes("iPad") || device.includes("Android")) {
      return <Smartphone className="h-3 w-3" />;
    }
    return <Monitor className="h-3 w-3" />;
  };

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Card className="bg-card border p-8">
        <div className="border-b pb-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Activity Log</h2>
              <p className="text-muted-foreground mt-2 text-sm">
                View your account activity history and security events.
              </p>
            </div>
            <div className="w-full sm:w-48">
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Events</SelectItem>
                  <SelectItem value="security">Security</SelectItem>
                  <SelectItem value="login">Login</SelectItem>
                  <SelectItem value="settings">Settings</SelectItem>
                  <SelectItem value="api">API</SelectItem>
                  <SelectItem value="content">Content</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <ScrollArea className="h-[600px] mt-6">
          <div className="space-y-4 pr-4">
            {filteredEvents.map((event) => (
              <div
                key={event.id}
                className={`rounded-lg border p-4 ${
                  event.critical ? "border-l-4 border-l-red-500" : ""
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`rounded-full p-2 mt-1 ${
                    event.type === "security" ? "bg-red-100 dark:bg-red-950" :
                    event.type === "login" ? "bg-blue-100 dark:bg-blue-950" :
                    event.type === "settings" ? "bg-green-100 dark:bg-green-950" :
                    event.type === "api" ? "bg-purple-100 dark:bg-purple-950" :
                    "bg-muted"
                  }`}>
                    {getEventIcon(event.type)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-1 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold">{event.action}</h3>
                        {getEventBadge(event.type)}
                        {event.success ? (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-red-600" />
                        )}
                      </div>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {event.timestamp}
                      </span>
                    </div>

                    <p className="text-sm text-muted-foreground mb-3">
                      {event.description}
                    </p>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Globe className="h-3 w-3" />
                        <span className="truncate">{event.ipAddress} • {event.location}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        {getDeviceIcon(event.device)}
                        <span className="truncate">{event.device}</span>
                      </div>
                      {event.critical && (
                        <div className="flex items-center gap-1 text-red-600">
                          <AlertCircle className="h-3 w-3" />
                          <span>Critical event</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="mt-6 rounded-lg bg-muted p-4">
          <p className="text-sm text-muted-foreground">
            <strong className="text-foreground">Activity Retention:</strong> Activity logs are kept for 90 days. Security-related events are retained for up to 2 years for compliance purposes.
          </p>
        </div>
      </Card>
    </div>
  );
}
