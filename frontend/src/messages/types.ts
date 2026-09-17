export type BilingualMessage = readonly [malagasy: string, english: string];

export type MessageCatalog = Readonly<Record<string, BilingualMessage>>;
