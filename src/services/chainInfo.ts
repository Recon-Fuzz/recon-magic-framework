import { ethers } from 'ethers';

const rpcUrl = `https://eth-mainnet.g.alchemy.com/v2/EN8-iA0eGN4NmGkKaMt_cF4MYWJAq0Vi`;

// Function to get the timestamp of the latest block or a specific block
export async function getBlockTimestamp(chain: string, blockNumber?: string): Promise<string> {
    const provider = new ethers.JsonRpcProvider(chain);

    try {
        let block;
        if (blockNumber === undefined || blockNumber === "LATEST" || "") {
            // Get the latest block if no block number is provided
            block = await provider.getBlock('latest');
        } else {
            // Get the block by its number if a block number is provided
            block = await provider.getBlock(Number(blockNumber));
        }

        if (!block) return "";

        return block.timestamp.toString();
    } catch (error) {
        console.error('Error fetching block:', error);
        throw error;
    }
}

export async function getLatestBlockNumber(chain: string): Promise<string> {
    const provider = new ethers.JsonRpcProvider(chain);

    try {
        // Fetch the latest block number
        const latestBlockNumber = await provider.getBlockNumber();
        
        // Return the block number as a string
        return latestBlockNumber.toString();
    } catch (error) {
        console.error('Error fetching latest block number:', error);
        throw error;
    }
}

