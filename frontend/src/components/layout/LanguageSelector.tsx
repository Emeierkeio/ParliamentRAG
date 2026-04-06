"use client";

import { useLocale, useTranslations } from 'next-intl';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function LanguageSelector() {
  const locale = useLocale();
  const t = useTranslations('LanguageSelector');
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const handleSwitch = () => {
    const nextLocale = locale === 'it' ? 'en' : 'it';
    // Set cookie for next-intl server-side resolution
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; SameSite=Lax`;
    // Update URL param
    const params = new URLSearchParams(searchParams.toString());
    if (nextLocale === 'it') {
      params.delete('lang');
    } else {
      params.set('lang', nextLocale);
    }
    const qs = params.toString();
    // Use window.location to trigger full reload (next-intl needs server re-render)
    window.location.href = `${pathname}${qs ? `?${qs}` : ""}`;
  };

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleSwitch}
      title={t('switchTo')}
      className="flex items-center gap-1.5 h-8 px-2 text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
    >
      <Globe className="h-4 w-4 shrink-0" />
      <span className="text-[12px] font-medium uppercase tracking-wide">
        {locale === 'it' ? 'IT' : 'EN'}
      </span>
    </Button>
  );
}
