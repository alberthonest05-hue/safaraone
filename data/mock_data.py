import random
from datetime import datetime

DESTINATIONS = [{'id': 'zanzibar',
  'name': 'Zanzibar',
  'country': 'Tanzania',
  'region': 'Zanzibar Archipelago',
  'tagline': 'The Spice Island Paradise',
  'description': "Zanzibar is a stunning semi-autonomous island off Tanzania's "
                 'coast, famous for its white-sand beaches, turquoise Indian '
                 'Ocean waters, and the UNESCO World Heritage-listed Stone '
                 'Town. A magical blend of African, Arab, and European '
                 'influences creates a unique cultural tapestry.',
  'image_url': 'https://images.unsplash.com/photo-1590523277543-a94d2e4eb00b?w=800',
  'gallery': ['https://source.unsplash.com/400x300/?zanzibar,scenic,1',
              'https://source.unsplash.com/400x300/?zanzibar,scenic,2',
              'https://source.unsplash.com/400x300/?zanzibar,scenic,3'],
  'latitude': -6.165917,
  'longitude': 39.202641,
  'average_daily_budget_usd': 80,
  'best_months': 'Jun–Oct, Dec–Feb',
  'language': 'Swahili, English',
  'currency': 'TZS / USD',
  'highlights': ['Stone Town',
                 'Nungwi Beach',
                 'Spice Tours',
                 'Dolphin Tours',
                 'Jozani Forest'],
  'stats': {'hotels': 42, 'experiences': 28, 'guides': 16}},
 {'id': 'serengeti',
  'name': 'Serengeti',
  'country': 'Tanzania',
  'region': 'Mara Region',
  'tagline': 'The Greatest Wildlife Show on Earth',
  'description': "The Serengeti is one of the world's most famous wildlife "
                 'sanctuaries, spanning 14,763 km². Witness the Great '
                 'Migration — over 1.5 million wildebeest, zebras, and '
                 "gazelles in an endless cycle of life. Home to the 'Big "
                 "Five': lion, leopard, elephant, buffalo, and rhino.",
  'image_url': 'https://images.unsplash.com/photo-1516426122078-c23e76319801?w=800',
  'gallery': ['https://source.unsplash.com/400x300/?serengeti,scenic,1',
              'https://source.unsplash.com/400x300/?serengeti,scenic,2',
              'https://source.unsplash.com/400x300/?serengeti,scenic,3'],
  'latitude': -2.333333,
  'longitude': 34.833333,
  'average_daily_budget_usd': 250,
  'best_months': 'Jun–Sep (Migration), Jan–Feb (Calving)',
  'language': 'Swahili, English, Maa',
  'currency': 'TZS / USD',
  'highlights': ['Great Migration',
                 'Hot Air Balloon Safari',
                 'Ngorongoro Crater',
                 'Maasai Villages',
                 'Balloon Sunrise'],
  'stats': {'hotels': 18, 'experiences': 14, 'guides': 12}},
 {'id': 'kilimanjaro',
  'name': 'Mount Kilimanjaro',
  'country': 'Tanzania',
  'region': 'Kilimanjaro Region',
  'tagline': 'Roof of Africa',
  'description': "Mount Kilimanjaro is Africa's highest peak at 5,895m and the "
                 "world's largest free-standing volcanic mountain. Trek "
                 'through five distinct ecological zones from tropical '
                 'rainforest to arctic summit. A bucket-list adventure that '
                 "doesn't require technical climbing skills.",
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'gallery': ['https://source.unsplash.com/400x300/?kilimanjaro,scenic,1',
              'https://source.unsplash.com/400x300/?kilimanjaro,scenic,2',
              'https://source.unsplash.com/400x300/?kilimanjaro,scenic,3'],
  'latitude': -3.067,
  'longitude': 37.359,
  'average_daily_budget_usd': 180,
  'best_months': 'Jan–Mar, Jun–Oct',
  'language': 'Swahili, English',
  'currency': 'TZS / USD',
  'highlights': ['Uhuru Peak',
                 'Machame Route',
                 'Lemosho Route',
                 'Marangu Route',
                 'Coffee Farms'],
  'stats': {'hotels': 24, 'experiences': 18, 'guides': 22}}]

ACCOMMODATIONS = [{'id': 'z-hotel-001',
  'destination_id': 'zanzibar',
  'name': 'Zanzibar White Sand Luxury Villas',
  'type': 'luxury resort',
  'tier': 'luxury',
  'price_per_night_usd': 420,
  'rating': 4.9,
  'review_count': 312,
  'amenities': ['Private Pool',
                'Beachfront',
                'Spa',
                'Restaurant',
                'Free WiFi',
                'Water Sports'],
  'description': 'Exclusive beachfront villas with private pools overlooking '
                 'the Indian Ocean. World-class spa and gourmet dining.',
  'image_url': 'https://images.unsplash.com/photo-1590523277543-a94d2e4eb00b?w=800',
  'latitude': -5.7167,
  'longitude': 39.3083,
  'booking_url': '#'},
 {'id': 'z-hotel-002',
  'destination_id': 'zanzibar',
  'name': 'Maru Maru Hotel Stone Town',
  'type': 'boutique hotel',
  'tier': 'mid-range',
  'price_per_night_usd': 95,
  'rating': 4.6,
  'review_count': 189,
  'amenities': ['Rooftop Bar',
                'Pool',
                'Free WiFi',
                'Air Conditioning',
                'Breakfast Included'],
  'description': 'Stylish boutique hotel in UNESCO World Heritage Stone Town. '
                 'Rooftop bar with panoramic ocean views.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'latitude': -6.165917,
  'longitude': 39.202641,
  'booking_url': '#'},
 {'id': 'z-hotel-003',
  'destination_id': 'zanzibar',
  'name': 'Coconut Grove Guesthouse',
  'type': 'guesthouse',
  'tier': 'budget',
  'price_per_night_usd': 28,
  'rating': 4.3,
  'review_count': 94,
  'amenities': ['Free WiFi',
                'Fan',
                'Shared Terrace',
                'Communal Kitchen',
                'Bicycle Rental'],
  'description': 'Friendly family-run guesthouse surrounded by coconut palms. '
                 'Perfect for backpackers and budget travelers.',
  'image_url': 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800',
  'latitude': -6.133,
  'longitude': 39.198,
  'booking_url': '#'},
 {'id': 'z-hotel-004',
  'destination_id': 'zanzibar',
  'name': 'Nungwi Dreams Resort',
  'type': 'resort',
  'tier': 'luxury',
  'price_per_night_usd': 310,
  'rating': 4.8,
  'review_count': 245,
  'amenities': ['Infinity Pool',
                'Dive Center',
                'Beachfront',
                'Spa',
                'Restaurant',
                'Bar'],
  'description': 'Stunning resort at Nungwi beach featuring an iconic infinity '
                 'pool. World-class diving and snorkeling.',
  'image_url': 'https://images.unsplash.com/photo-1590523277543-a94d2e4eb00b?w=800',
  'latitude': -5.7245,
  'longitude': 39.2968,
  'booking_url': '#'},
 {'id': 'z-hotel-005',
  'destination_id': 'zanzibar',
  'name': 'The Swahili House',
  'type': 'boutique hotel',
  'tier': 'mid-range',
  'price_per_night_usd': 75,
  'rating': 4.5,
  'review_count': 128,
  'amenities': ['Courtyard Garden',
                'Free WiFi',
                'Air Conditioning',
                'Breakfast',
                'Spice Tour'],
  'description': 'A beautifully restored traditional Swahili house in Stone '
                 'Town. Authentic architecture with modern comforts.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'latitude': -6.162,
  'longitude': 39.197,
  'booking_url': '#'},
 {'id': 's-lodge-001',
  'destination_id': 'serengeti',
  'name': 'Four Seasons Safari Lodge Serengeti',
  'type': 'safari lodge',
  'tier': 'luxury',
  'price_per_night_usd': 1200,
  'rating': 5.0,
  'review_count': 418,
  'amenities': ['Private Safari',
                'Infinity Pool',
                'Spa',
                'Observatory',
                'Helicopter Transfers',
                'Gourmet Dining'],
  'description': 'Ultra-luxury safari lodge perched above a natural watering '
                 'hole with 360° wildlife views. The pinnacle of African '
                 'safari.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'latitude': -2.333,
  'longitude': 34.833,
  'booking_url': '#'},
 {'id': 's-lodge-002',
  'destination_id': 'serengeti',
  'name': 'Serengeti Sopa Lodge',
  'type': 'safari lodge',
  'tier': 'mid-range',
  'price_per_night_usd': 250,
  'rating': 4.6,
  'review_count': 204,
  'amenities': ['Game Drives',
                'Pool',
                'Restaurant',
                'Bar',
                'Bird Watching',
                'Sunrise Walks'],
  'description': 'Comfortable mid-range lodge with excellent game viewing and '
                 'stunning savanna panoramas. Ideal for families.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'latitude': -2.419,
  'longitude': 34.775,
  'booking_url': '#'},
 {'id': 's-camp-001',
  'destination_id': 'serengeti',
  'name': 'Wilde Camp Serengeti',
  'type': 'tented camp',
  'tier': 'budget',
  'price_per_night_usd': 80,
  'rating': 4.4,
  'review_count': 67,
  'amenities': ['Shared Facilities',
                'Camp Fires',
                'Game Drives',
                'Meals Included'],
  'description': 'Authentic tented camping experience in the heart of the '
                 'Serengeti. Wake up to the sounds of the wild.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'latitude': -2.266,
  'longitude': 34.821,
  'booking_url': '#'},
 {'id': 'k-hotel-001',
  'destination_id': 'kilimanjaro',
  'name': 'Arusha Coffee Lodge',
  'type': 'boutique hotel',
  'tier': 'luxury',
  'price_per_night_usd': 280,
  'rating': 4.9,
  'review_count': 276,
  'amenities': ['Coffee Plantation',
                'Spa',
                'Pool',
                'Restaurant',
                'Mountain Views',
                'Bike Tours'],
  'description': 'Set on a working coffee estate with stunning Kilimanjaro '
                 'views. The perfect pre/post-climb retreat.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'latitude': -3.368,
  'longitude': 36.682,
  'booking_url': '#'},
 {'id': 'k-hotel-002',
  'destination_id': 'kilimanjaro',
  'name': 'Springlands Hotel Moshi',
  'type': 'hotel',
  'tier': 'mid-range',
  'price_per_night_usd': 65,
  'rating': 4.4,
  'review_count': 153,
  'amenities': ['Pool',
                'Free WiFi',
                'Restaurant',
                'Bar',
                'Trekking Support',
                'Gear Storage'],
  'description': "Popular climbers' base near Kilimanjaro gate. Excellent "
                 'trekking logistics and friendly staff experience.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'latitude': -3.354,
  'longitude': 37.329,
  'booking_url': '#'},
 {'id': 'k-hostel-001',
  'destination_id': 'kilimanjaro',
  'name': 'Keys Hotel Moshi',
  'type': 'guesthouse',
  'tier': 'budget',
  'price_per_night_usd': 22,
  'rating': 4.1,
  'review_count': 88,
  'amenities': ['Free WiFi',
                'Garden',
                'Communal Kitchen',
                'Laundry',
                'Tour Booking'],
  'description': 'Budget-friendly accommodation in Moshi town. Great base for '
                 'Kilimanjaro treks without breaking the bank.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'latitude': -3.352,
  'longitude': 37.335,
  'booking_url': '#'}]

EXPERIENCES = [{'id': 'ze-001',
  'destination_id': 'zanzibar',
  'title': 'Spice Farm Tour & Swahili Cooking Class',
  'category': 'food & culture',
  'tier': 'budget',
  'price_usd': 35,
  'duration_hours': 4,
  'rating': 4.8,
  'review_count': 521,
  'max_participants': 12,
  'description': 'Walk through aromatic spice farms growing cloves, cinnamon, '
                 'vanilla, and nutmeg. Learn to cook authentic Swahili dishes '
                 'with a local chef.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'tags': ['food', 'culture', 'spices', 'cooking'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ze-002',
  'destination_id': 'zanzibar',
  'title': 'Stone Town Heritage Walking Tour',
  'category': 'sightseeing',
  'tier': 'budget',
  'price_usd': 25,
  'duration_hours': 3,
  'rating': 4.7,
  'review_count': 389,
  'max_participants': 10,
  'description': 'Explore the labyrinthine alleys of Stone Town, a UNESCO '
                 "World Heritage Site. Visit the Old Fort, Freddie Mercury's "
                 'birthplace, and vibrant local markets.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'tags': ['history', 'culture', 'walking', 'heritage'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ze-003',
  'destination_id': 'zanzibar',
  'title': 'Dolphin & Snorkeling Safari',
  'category': 'adventure',
  'tier': 'mid-range',
  'price_usd': 65,
  'duration_hours': 5,
  'rating': 4.9,
  'review_count': 612,
  'max_participants': 8,
  'description': 'Swim with wild spinner dolphins in their natural habitat at '
                 'Kizimkazi. Snorkel colorful coral reefs and spot tropical '
                 'fish, sea turtles, and starfish.',
  'image_url': 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800',
  'tags': ['dolphins', 'snorkeling', 'ocean', 'wildlife'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ze-004',
  'destination_id': 'zanzibar',
  'title': 'Sunset Dhow Cruise with Seafood Dinner',
  'category': 'food & culture',
  'tier': 'mid-range',
  'price_usd': 85,
  'duration_hours': 3,
  'rating': 4.9,
  'review_count': 445,
  'max_participants': 20,
  'description': 'Sail on a traditional wooden dhow as the sun sets over the '
                 'Indian Ocean. Enjoy freshly caught seafood and cocktails '
                 'with breathtaking views.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'tags': ['sunset', 'sailing', 'seafood', 'romance'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ze-005',
  'destination_id': 'zanzibar',
  'title': 'Rock Restaurant Exclusive Dining Experience',
  'category': 'food & culture',
  'tier': 'luxury',
  'price_usd': 150,
  'duration_hours': 2,
  'rating': 4.8,
  'review_count': 287,
  'max_participants': 6,
  'description': 'Dine at the world-famous Rock Restaurant — built on a coral '
                 'rock in the middle of the Indian Ocean. Fresh seafood, '
                 'lobster, and fine wines.',
  'image_url': 'https://images.unsplash.com/photo-1568702846914-96b305d2aaeb?w=800',
  'tags': ['fine dining', 'seafood', 'iconic', 'romance'],
  'is_indoor': True,
  'booking_url': '#'},
 {'id': 'ze-006',
  'destination_id': 'zanzibar',
  'title': 'Jozani Forest & Red Colobus Monkey Walk',
  'category': 'wildlife',
  'tier': 'budget',
  'price_usd': 28,
  'duration_hours': 3,
  'rating': 4.6,
  'review_count': 334,
  'max_participants': 15,
  'description': "Visit Zanzibar's last ancient forest and meet the endemic "
                 "Zanzibar Red Colobus Monkey — one of Africa's rarest "
                 'primates. Stunning mangrove boardwalk.',
  'image_url': 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800',
  'tags': ['wildlife', 'primates', 'forest', 'nature'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'se-001',
  'destination_id': 'serengeti',
  'title': 'Full-Day Big Five Game Drive',
  'category': 'wildlife',
  'tier': 'mid-range',
  'price_usd': 185,
  'duration_hours': 10,
  'rating': 5.0,
  'review_count': 892,
  'max_participants': 6,
  'description': 'Track the Big Five — lion, leopard, elephant, buffalo, and '
                 'rhino — across vast golden savanna. Expert wildlife guide. '
                 'All-inclusive game drive in 4WD vehicle.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'tags': ['big five', 'safari', 'wildlife', '4WD'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'se-002',
  'destination_id': 'serengeti',
  'title': 'Hot Air Balloon Safari at Sunrise',
  'category': 'adventure',
  'tier': 'luxury',
  'price_usd': 550,
  'duration_hours': 4,
  'rating': 4.9,
  'review_count': 344,
  'max_participants': 12,
  'description': 'Float above the Serengeti at sunrise in a hot air balloon. '
                 'Witness the Great Migration from above. Champagne bush '
                 'breakfast upon landing.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'tags': ['balloon', 'sunrise', 'luxury', 'migration'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'se-003',
  'destination_id': 'serengeti',
  'title': 'Maasai Village Cultural Immersion',
  'category': 'food & culture',
  'tier': 'budget',
  'price_usd': 45,
  'duration_hours': 3,
  'rating': 4.7,
  'review_count': 228,
  'max_participants': 10,
  'description': 'Visit an authentic Maasai village. Learn about traditional '
                 'life, warrior culture, beadwork, and songs. Participate in a '
                 'traditional jumping ceremony.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'tags': ['maasai', 'culture', 'traditional', 'community'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'se-004',
  'destination_id': 'serengeti',
  'title': 'Ngorongoro Crater Day Safari',
  'category': 'wildlife',
  'tier': 'mid-range',
  'price_usd': 220,
  'duration_hours': 12,
  'rating': 5.0,
  'review_count': 673,
  'max_participants': 6,
  'description': "Descend into the world's largest intact volcanic caldera — a "
                 'natural Eden. See thousands of animals in the densest '
                 'concentration on Earth.',
  'image_url': 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800',
  'tags': ['crater', 'wildlife', 'UNESCO', 'rare animals'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ke-001',
  'destination_id': 'kilimanjaro',
  'title': '7-Day Machame Route Summit Trek',
  'category': 'adventure',
  'tier': 'luxury',
  'price_usd': 1800,
  'duration_hours': 168,
  'rating': 4.8,
  'review_count': 456,
  'max_participants': 8,
  'description': "Conquer Africa's highest peak via the scenic Machame "
                 "'Whiskey' Route. All-inclusive: park fees, guides, porters, "
                 'meals, and camping equipment.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'tags': ['trekking', 'summit', 'challenge', 'all-inclusive'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ke-002',
  'destination_id': 'kilimanjaro',
  'title': 'Coffee Farm Day Tour & Tasting',
  'category': 'food & culture',
  'tier': 'budget',
  'price_usd': 40,
  'duration_hours': 5,
  'rating': 4.7,
  'review_count': 189,
  'max_participants': 12,
  'description': "Visit a Chagga coffee farm on Kilimanjaro's fertile slopes. "
                 'Learn the entire coffee journey from bean to cup. '
                 'Traditional lunch included.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'tags': ['coffee', 'culture', 'chagga', 'farming'],
  'is_indoor': False,
  'booking_url': '#'},
 {'id': 'ke-003',
  'destination_id': 'kilimanjaro',
  'title': 'Kilimanjaro Forest Hike & Waterfall Trek',
  'category': 'adventure',
  'tier': 'budget',
  'price_usd': 55,
  'duration_hours': 6,
  'rating': 4.6,
  'review_count': 134,
  'max_participants': 10,
  'description': "Trek through lush montane forest on Kilimanjaro's lower "
                 'slopes. Discover hidden waterfalls, wildlife, and stunning '
                 'mountain views without a summit attempt.',
  'image_url': 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800',
  'tags': ['hiking', 'waterfall', 'forest', 'day trip'],
  'is_indoor': False,
  'booking_url': '#'}]

GUIDES = [{'id': 'guide-001',
  'destination_id': 'zanzibar',
  'name': 'Amani Juma',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Stone Town Heritage Expert',
  'languages': ['Swahili', 'English', 'Arabic'],
  'specializations': ['cultural', 'food', 'history'],
  'price_per_day_usd': 75,
  'rating': 4.9,
  'total_reviews': 284,
  'experience_years': 12,
  'bio': "Born and raised in Stone Town, I grew up in the heart of Zanzibar's "
         'history. I bring visitors into the real Stone Town — hidden '
         'alleyways, family spice gardens, and the true essence of Swahili '
         'culture.',
  'certifications': ['TTB Certified', 'First Aid'],
  'availability': 'Year-round',
  'is_verified': True},
 {'id': 'guide-002',
  'destination_id': 'zanzibar',
  'name': 'Fatuma Hassan',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Ocean & Marine Life Specialist',
  'languages': ['Swahili', 'English', 'French'],
  'specializations': ['adventure', 'wildlife', 'diving'],
  'price_per_day_usd': 90,
  'rating': 5.0,
  'total_reviews': 198,
  'experience_years': 8,
  'bio': "PADI certified dive master with a passion for Zanzibar's incredible "
         "marine biodiversity. I'll take you to secret coral gardens, dolphin "
         'bays, and turtle nesting sites that most visitors never see.',
  'certifications': ['TTB Certified', 'PADI Divemaster', 'Marine Conservation'],
  'availability': 'Jun–Apr',
  'is_verified': True},
 {'id': 'guide-003',
  'destination_id': 'zanzibar',
  'name': 'Khalid Omar',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Spice & Food Tourism Guide',
  'languages': ['Swahili', 'English'],
  'specializations': ['food', 'cultural', 'photography'],
  'price_per_day_usd': 60,
  'rating': 4.8,
  'total_reviews': 156,
  'experience_years': 6,
  'bio': 'My family has farmed spices for four generations. I offer the most '
         'authentic spice and food tour on the island — taste fresh vanilla, '
         'cloves, black pepper, and create your own spice blend to take home.',
  'certifications': ['TTB Certified'],
  'availability': 'Year-round',
  'is_verified': True},
 {'id': 'guide-004',
  'destination_id': 'serengeti',
  'name': 'Daniel Oloibon',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Maasai Wildlife Tracker & Safari Expert',
  'languages': ['Swahili', 'English', 'Maa'],
  'specializations': ['wildlife', 'cultural', 'photography'],
  'price_per_day_usd': 220,
  'rating': 5.0,
  'total_reviews': 412,
  'experience_years': 18,
  'bio': 'A Maasai warrior turned master tracker, I read the Serengeti like a '
         'book. I know where the lions sleep, where the leopards hunt at dusk, '
         'and exactly where the migration will cross next. Safari is not just '
         "a game drive — it's a story.",
  'certifications': ['TTB Certified', 'Safari Guide Level 4', 'First Aid'],
  'availability': 'Year-round',
  'is_verified': True},
 {'id': 'guide-005',
  'destination_id': 'serengeti',
  'name': 'Grace Mwangi',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Ornithologist & Birding Specialist',
  'languages': ['Swahili', 'English', 'German'],
  'specializations': ['wildlife', 'birding', 'photography'],
  'price_per_day_usd': 180,
  'rating': 4.9,
  'total_reviews': 167,
  'experience_years': 11,
  'bio': 'With over 500 bird species recorded personally in the Serengeti '
         "ecosystem, I offer specialized birding safaris. Whether you're a "
         "twitcher or a casual wildlife lover, I'll open your eyes to a world "
         "you've never noticed.",
  'certifications': ['TTB Certified',
                     'Professional Field Guide',
                     'Ornithology Diploma'],
  'availability': 'Year-round',
  'is_verified': True},
 {'id': 'guide-006',
  'destination_id': 'kilimanjaro',
  'name': 'Baraka Moshi',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Kilimanjaro Summit Specialist',
  'languages': ['Swahili', 'English'],
  'specializations': ['adventure', 'trekking', 'altitude'],
  'price_per_day_usd': 130,
  'rating': 4.9,
  'total_reviews': 523,
  'experience_years': 15,
  'bio': 'I have guided over 800 summits of Kilimanjaro. My 98% success rate '
         'comes from careful acclimatization, mental coaching, and knowing '
         "every route's secrets. Pole pole — slowly slowly — together we reach "
         'the Roof of Africa.',
  'certifications': ['TTB Certified',
                     'Advanced Wilderness First Aid',
                     'Kilimanjaro Expert'],
  'availability': 'Year-round (peak: Jan–Mar, Jun–Oct)',
  'is_verified': True},
 {'id': 'guide-007',
  'destination_id': 'kilimanjaro',
  'name': 'Neema Chagga',
  'avatar_url': 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800',
  'title': 'Chagga Culture & Coffee Guide',
  'languages': ['Swahili', 'English', 'Chagga'],
  'specializations': ['cultural', 'food', 'trekking'],
  'price_per_day_usd': 85,
  'rating': 4.8,
  'total_reviews': 203,
  'experience_years': 9,
  'bio': "As a Chagga woman from Kilimanjaro's slopes, I share the hidden "
         'culture of my people — their ancient irrigation systems, coffee '
         'traditions, banana beer brewing, and mountain folklore that spans '
         'generations.',
  'certifications': ['TTB Certified', 'Cultural Heritage Guide'],
  'availability': 'Year-round',
  'is_verified': True}]


def get_destination_by_id(dest_id: str):
    return next((d for d in DESTINATIONS if d["id"] == dest_id), None)

def get_accommodations_by_destination(dest_id: str):
    return [a for a in ACCOMMODATIONS if a["destination_id"] == dest_id]

def get_experiences_by_destination(dest_id: str):
    return [e for e in EXPERIENCES if e["destination_id"] == dest_id]

def get_guides_by_destination(dest_id: str):
    return [g for g in GUIDES if g["destination_id"] == dest_id]

def generate_itinerary(destination_id: str, budget_usd: float, days: int, travelers: int) -> dict:
    dest = get_destination_by_id(destination_id)
    if not dest:
        return {"error": "Destination not found"}

    stays = get_accommodations_by_destination(destination_id)
    exps  = get_experiences_by_destination(destination_id)
    guides_list = get_guides_by_destination(destination_id)

    per_person_budget = budget_usd / travelers

    accom_budget_per_night = (per_person_budget * 0.50) / days
    suitable_stays = sorted(
        [s for s in stays if s["price_per_night_usd"] <= accom_budget_per_night * 1.3],
        key=lambda x: x["rating"],
        reverse=True
    )
    chosen_stay = suitable_stays[0] if suitable_stays else stays[-1]
    stay_total = chosen_stay["price_per_night_usd"] * days

    guide_budget = per_person_budget * 0.20
    suitable_guides = sorted(
        [g for g in guides_list if g["price_per_day_usd"] <= guide_budget],
        key=lambda x: x["rating"],
        reverse=True
    )
    chosen_guide = suitable_guides[0] if suitable_guides else None

    remaining = per_person_budget - stay_total
    if chosen_guide:
        remaining -= chosen_guide["price_per_day_usd"]

    chosen_experiences = []
    exp_pool = sorted(exps, key=lambda x: x["rating"], reverse=True)
    for exp in exp_pool:
        if remaining >= exp["price_usd"] and len(chosen_experiences) < days + 1:
            chosen_experiences.append(exp)
            remaining -= exp["price_usd"]

    itinerary_days = []
    exp_idx = 0
    for day_num in range(1, days + 1):
        day_exp = chosen_experiences[exp_idx] if exp_idx < len(chosen_experiences) else None
        if day_exp:
            exp_idx += 1
        itinerary_days.append({
            "day": day_num,
            "date_label": f"Day {day_num}",
            "accommodation": chosen_stay,
            "experience": day_exp,
            "guide": chosen_guide if day_num == 1 else None,
            "day_cost_usd": (
                chosen_stay["price_per_night_usd"]
                + (day_exp["price_usd"] if day_exp else 0)
                + (chosen_guide["price_per_day_usd"] if chosen_guide and day_num == 1 else 0)
            )
        })

    total_cost = sum(d["day_cost_usd"] for d in itinerary_days)
    savings = per_person_budget - total_cost

    return {
        "destination": dest,
        "days": days,
        "travelers": travelers,
        "budget_usd": budget_usd,
        "total_cost_usd": round(total_cost, 2),
        "savings_usd": round(max(savings, 0), 2),
        "budget_utilization_pct": round(min((total_cost / per_person_budget) * 100, 100), 1),
        "itinerary": itinerary_days,
        "summary": {
            "accommodation": chosen_stay["name"],
            "accommodation_tier": chosen_stay["tier"],
            "guide": chosen_guide["name"] if chosen_guide else "Self-guided",
            "experiences_count": len(chosen_experiences),
            "tip": _generate_tip(destination_id, per_person_budget),
        }
    }

def _generate_tip(destination_id: str, budget: float) -> str:
    tips = {
        "zanzibar": [
            "Book dolphin tours early morning for the best sightings at Kizimkazi.",
            "Forodhani Night Market in Stone Town is a must — $5 fills you up royally.",
            "Negotiate spice prices at Darajani Market using Swahili phrases.",
        ],
        "serengeti": [
            "June–October offers the best Great Migration river crossing views.",
            "Early morning (6–9am) and late afternoon (4–7pm) are prime animal activity times.",
            "Pack light layers — mornings on the savanna can be surprisingly cold.",
        ],
        "kilimanjaro": [
            "Spend an extra acclimatization day — your summit chances increase by 40%.",
            "Pack high-energy snacks like nuts, chocolate, and dried fruit for the summit push.",
            "Hire local porters — they're essential support and it directly helps the community.",
        ]
    }
    import random
    dest_tips = tips.get(destination_id, ["Enjoy your Tanzania adventure!"])
    return random.choice(dest_tips)
