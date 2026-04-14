interface TabsProps {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}

export default function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <div className="flex border-b border-border mb-4">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
            active === tab
              ? 'border-accent text-accent'
              : 'border-transparent text-text-muted hover:text-text-primary hover:border-border'
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
