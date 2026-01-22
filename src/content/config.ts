import { defineCollection, z } from 'astro:content';

const news = defineCollection({
	schema: z.object({
		title: z.string(),
		pubDate: z.coerce.date(),
		description: z.string(),
		tags: z.array(z.string()),
	}),
});

export const collections = { news };
