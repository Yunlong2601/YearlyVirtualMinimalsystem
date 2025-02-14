import shelve

class RewardSystem:
    def add_reward(self, reward_name, points_required, quantity, image_url=None):

        with shelve.open("rewards_db", writeback=True) as rewards:
            rewards[reward_name] = {
                "points": points_required,
                "quantity": quantity,
                "image_url": image_url  # Store the image URL
            }
            print(f"Added reward: {reward_name} for {points_required} points with quantity {quantity}. "
                  f"Image URL: {image_url if image_url else 'Not provided'}.")

    def remove_reward(self, reward_name):

        with shelve.open("rewards_db", writeback=True) as rewards:
            if reward_name in rewards:
                del rewards[reward_name]
                print(f"Removed reward: {reward_name}.")
            else:
                print(f"Reward '{reward_name}' does not exist.")

    def view_rewards(self):
        with shelve.open("rewards_db") as rewards:
            if not rewards:
                print("No rewards available.")
                return
            print("Available Rewards:")
            for reward_name, data in rewards.items():
                print(f"- {reward_name}: {data['points']} points, Quantity: {data['quantity']}, "
                      f"Image URL: {data.get('image_url', 'Not provided')}")

    def get_rewards(self):
        with shelve.open("rewards_db") as rewards:
            return dict(rewards)