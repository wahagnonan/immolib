type ModuleHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
};

export function ModuleHeader({
  eyebrow,
  title,
  description,
  action,
}: ModuleHeaderProps) {
  return (
    <section className="flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted sm:text-base">
          {description}
        </p>
      </div>
      {action}
    </section>
  );
}
