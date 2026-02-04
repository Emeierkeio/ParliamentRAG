
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AuthorityWeights {
    [key: string]: number;
}

interface WeightsEditorProps {
    weights: AuthorityWeights;
    onChange: (newWeights: AuthorityWeights) => void;
}

export function WeightsEditor({ weights, onChange }: WeightsEditorProps) {
    const handleChange = (key: string, value: string) => {
        const numValue = parseFloat(value);
        if (!isNaN(numValue)) {
            onChange({
                ...weights,
                [key]: numValue
            });
        }
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Pesi Livello Autorità</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
                {Object.entries(weights).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-3 items-center gap-4">
                        <Label className="capitalize col-span-1">{key}</Label>
                        <Input 
                            type="number" 
                            step="0.05" 
                            min="0" 
                            max="1" 
                            value={value} 
                            onChange={(e) => handleChange(key, e.target.value)}
                            className="col-span-2"
                        />
                    </div>
                ))}
            </CardContent>
        </Card>
    );
}

interface ManualAuthorities {
    [topic: string]: {
        [group: string]: string;
    }
}

interface ManualAuthoritiesEditorProps {
    authorities: ManualAuthorities;
    onChange: (newAuths: ManualAuthorities) => void;
}

// Simple editor for Manual Authorities (JSON-like structure but simplified UI)
// For now, let's keep it simple: just visualize and maybe basic edit if time permits.
// Editing nested dictionary structure dynamically is complex. 
// Let's focus on Weights first, and maybe a text area for each topic in Manual Authorities.

export function ManualAuthoritiesEditor({ authorities, onChange }: ManualAuthoritiesEditorProps) {
    // This is a placeholder for a more complex editor.
    // Implementing a full CRUD for nested objects is involved.
    // For MVP, we can iterate over topics.
    
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg">Autorità Manuali</CardTitle>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                    Configura esperti specifici per tema e gruppo.
                </p>
                {Object.keys(authorities).length === 0 ? (
                    <div className="text-sm text-gray-500 italic">Nessuna autorità manuale configurata. Usa l'editor JSON per aggiungerne di nuove.</div>
                ) : (
                    <div className="space-y-4">
                        {Object.entries(authorities).map(([topic, groupMap]) => (
                            <div key={topic} className="border p-3 rounded-md">
                                <h4 className="font-bold mb-2 capitalize">{topic}</h4>
                                <ul className="text-sm space-y-1">
                                    {Object.entries(groupMap).map(([group, name]) => (
                                        <li key={group} className="flex justify-between border-b pb-1 last:border-0">
                                            <span className="font-semibold text-xs">{group}:</span>
                                            <span>{name}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
