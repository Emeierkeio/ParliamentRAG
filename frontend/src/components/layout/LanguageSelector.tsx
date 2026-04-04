"use client";

import { useLocale, useTranslations } from 'next-intl';
import { Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function LanguageSelector() {
  const locale = useLocale();
  const t = useTranslations('LanguageSelector');

  const handleSwitch = () => {
    const nextLocale = locale === 'it' ? 'en' : 'it';
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; SameSite=Lax`;
    window.location.reload();
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
