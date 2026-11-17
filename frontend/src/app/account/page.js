'use client';

import { DashboardNav } from '@/components/nav';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useUser } from '@/context/user-context';
import { useToast } from '@/hooks/use-toast';
import { api } from '@/lib/api';
import { AISettings } from '@/components/ai-settings';
import { Suspense, useState } from 'react';

function AccountContent() {
  const { user, refreshUser } = useUser();
  const [isEditingEmail, setIsEditingEmail] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const { toast } = useToast();

  const isValidEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  if (!user) return null;

  const handleUpdateEmail = async () => {
    if (!newEmail.trim() || !isValidEmail(newEmail)) {
      toast({
        title: 'Invalid Input',
        description: 'Please enter a valid email address',
        variant: 'destructive',
        duration: 3000,
      });
      return;
    }

    try {
      await api.updateEmail(newEmail);
      await refreshUser();
      setIsEditingEmail(false);
      toast({
        title: 'Email updated successfully',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Failed to update email',
        description: error.message,
        variant: 'destructive',
        duration: 3000,
      });
    }
  };

  return (
    <div className="container py-8 space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Account</h1>
      </div>

      <AISettings />
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center space-x-4">
            <Avatar>
              <AvatarFallback>
                {user.username.slice(0, 2).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="space-y-1">
              <p className="text-sm font-medium leading-none">
                {user.username}
              </p>
              {isEditingEmail ? (
                <div className="flex gap-2 items-center mt-2">
                  <Input
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="h-8"
                  />
                  <Button size="sm" onClick={handleUpdateEmail}>
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setIsEditingEmail(false);
                      setNewEmail(user.email || '');
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground">
                    {user.email || 'No email set'}
                  </p>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setIsEditingEmail(true);
                      setNewEmail(user.email || '');
                    }}
                  >
                    Edit
                  </Button>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">Legacy credits: {user.credits}. AI gameplay now uses your own provider; buying game credits is not required.</p>
    </div>
  );
}

export default function AccountPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DashboardNav />
      <main className="flex-1 px-4">
        <Suspense fallback={<div>Loading...</div>}>
          <AccountContent />
        </Suspense>
      </main>
    </div>
  );
}
