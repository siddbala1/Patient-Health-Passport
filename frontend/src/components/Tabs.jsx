import { useState } from 'react';

export default function Tabs({ tabs }) {
  const [active, setActive] = useState(0);

  return (
    <div className="tabs">
      <div className="tabs__nav" role="tablist">
        {tabs.map((tab, i) => (
          <button
            key={i}
            role="tab"
            aria-selected={active === i}
            className={`tabs__btn${active === i ? ' tabs__btn--active' : ''}`}
            onClick={() => setActive(i)}
          >
            {tab.label}
            {tab.count != null && (
              <span className="tabs__count">{tab.count}</span>
            )}
          </button>
        ))}
      </div>
      <div className="tabs__panel" role="tabpanel">
        {tabs[active].content}
      </div>
    </div>
  );
}
